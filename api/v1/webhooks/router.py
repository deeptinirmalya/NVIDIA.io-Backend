import logging
import hmac
import hashlib
import json

from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, select

from db.models.single_registration import (
    SingleRegistration,
    SingleRegistrationStatus,
    SingleRegistrationPaymentStatus
)

from db.models.team_registration import (
    TeamRegistration,
    TeamRegistrationStatus,
    TeamRegistrationPaymentStatus
)

from db.models.payment import (
    Payment,
    PaymentStatus
)

from db.models.webhook_events import WebhookEvent

from db.session import get_db
from utils import auth_util
from engine.cache import acquire_payment_lock, release_payment_lock
from core.config import settings


logger = logging.getLogger("webhook")

webhook_router = APIRouter()

RAZORPAY_WEBHOOK_SECRET = settings.RAZORPAY_WEBHOOK_SECRET


def verify_razorpay_signature(body: bytes, signature: str) -> bool:
    expected_signature = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


@webhook_router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_razorpay_signature: str = Header(...)
):

    try:
        raw_body = await request.body()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read request body"
        )

    valid_razorpay_webhook = verify_razorpay_signature(raw_body,x_razorpay_signature)

    if not valid_razorpay_webhook:
        logger.warning("Razorpay webhook signature verification failed")
        raise HTTPException(
            status_code=403,
            detail="Invalid signature"
        )

    webhook_event_id = request.headers.get("x-razorpay-event-id")

    if not webhook_event_id:
        raise HTTPException(status_code=400,detail="Missing Razorpay event ID")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400,detail="Invalid JSON payload")

    payload = body.get("payload", {})
    payment = payload.get("payment", {}).get("entity", {})
    notes = payment.get("notes") or {}

    event = body.get("event")

    payment_id = payment.get("id")
    order_id = payment.get("order_id")
    payment_status = payment.get("status")
    amount = payment.get("amount")
    currency = payment.get("currency")
    method = payment.get("method")

    event_id = notes.get("event_id")

    participation_type = notes.get("participation_type")
    participation_id = notes.get("participation_id")
    user_id = notes.get("user_id")

    error_code = payment.get("error_code")
    error_description = payment.get("error_description")
    error_source = payment.get("error_source")
    error_step = payment.get("error_step")
    error_reason = payment.get("error_reason")

    if not event:
        raise HTTPException(status_code=400,detail="Missing webhook event type")

    if not payment_id or not order_id:
        raise HTTPException(status_code=400,detail="Missing payment ID or order ID")

    new_webhook_event = WebhookEvent(
        event_id=webhook_event_id,
        event_type=event,
        payload=body,
        processed=False,
        created_at=auth_util.get_now_utc()
    )
    db.add(new_webhook_event)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()

        logger.info(f"Duplicate Razorpay webhook received: {webhook_event_id}")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Webhook already received",
                "data": None,
                "error": None
            }
        )


    if event == "payment.captured":

        payment_record = (
            await db.execute(
                select(Payment).where(
                    Payment.razorpay_order_id == order_id
                )
            )
        ).scalar_one_or_none()

        if payment_record is None:
            await db.rollback()

            logger.warning(
                f"Payment not found for webhook: "
                f"payment_id={payment_id}, "
                f"order_id={order_id}"
            )

            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )

        lock_token, lock_key = await acquire_payment_lock(payment_record.id)

        if lock_token is None:
            await db.rollback()

            raise HTTPException(status_code=409,detail="Payment is currently being processed")
            

        try:
            await db.refresh(payment_record)

            current_status = payment_record.status

            # CREATED or PROCESSING -> SUCCESS
            if current_status in (PaymentStatus.CREATED,PaymentStatus.PROCESSING):
                payment_result = await db.execute(
                    update(Payment)
                    .where(
                        Payment.id == payment_record.id,
                        Payment.status.in_([
                            PaymentStatus.CREATED,
                            PaymentStatus.PROCESSING
                        ])
                    )
                    .values(
                        status=PaymentStatus.SUCCESS
                    )
                )

                if payment_result.rowcount == 0:
                    await db.rollback()

                    raise HTTPException(status_code=409,detail="Payment state changed during processing")

                if participation_type == "SINGLE":
                    registration_result = await db.execute(
                        update(SingleRegistration)
                        .where(
                            SingleRegistration.user_id == user_id,
                            SingleRegistration.event_id == event_id,
                            SingleRegistration.id == participation_id,
                        )
                        .values(
                            status=SingleRegistrationStatus.CONFIRMED,
                            payment_status=SingleRegistrationPaymentStatus.PAID,
                        )
                    )

                elif participation_type == "TEAM":
                    registration_result = await db.execute(
                        update(TeamRegistration)
                        .where(
                            TeamRegistration.captain_id == user_id,
                            TeamRegistration.event_id == event_id,
                            TeamRegistration.id == participation_id,
                        )
                        .values(
                            status=TeamRegistrationStatus.CONFIRMED,
                            payment_status=TeamRegistrationPaymentStatus.PAID,
                        )
                    )

                else:
                    await db.rollback()

                    logger.warning(f"Invalid participation type: {participation_type}")
                    raise HTTPException(status_code=400, detail="Invalid participation type")

                if registration_result.rowcount == 0:
                    await db.rollback()

                    logger.warning(
                        f"No registration updated. "
                        f"event={event}, "
                        f"type={participation_type}, "
                        f"id={participation_id}"
                    )

                    raise HTTPException(
                        status_code=404,
                        detail="Registration not found"
                    )

            elif current_status == PaymentStatus.SUCCESS:

                logger.info(f"Payment already SUCCESS: {payment_id}")

            elif current_status == PaymentStatus.FAILED:
                logger.warning(f"Ignoring captured webhook because payment is already FAILED: {payment_id}")


            new_webhook_event.processed = True
            new_webhook_event.processed_at = auth_util.get_now_utc()
            await db.commit()
        except HTTPException:
            raise
        except Exception:
            await db.rollback()

            logger.exception(f"Failed processing payment.captured webhook: {webhook_event_id}")

            raise HTTPException(status_code=500,detail="Webhook processing failed")

        finally:
            await release_payment_lock(lock_key,lock_token)

    elif event == "payment.failed":
        payment_record = (
            await db.execute(
                select(Payment).where(
                    Payment.razorpay_order_id == order_id
                )
            )
        ).scalar_one_or_none()

        if payment_record is None:
            await db.rollback()

            logger.warning(
                f"Payment not found for failed webhook: "
                f"payment_id={payment_id}, "
                f"order_id={order_id}"
            )

            raise HTTPException(status_code=404,detail="Payment not found")

        lock_token, lock_key = await acquire_payment_lock(payment_record.id)

        if lock_token is None:
            await db.rollback()

            raise HTTPException(status_code=409,detail="Payment is currently being processed")

        try:
            await db.refresh(payment_record)

            current_status = payment_record.status

            if current_status in (
                PaymentStatus.CREATED,
                PaymentStatus.PROCESSING
            ):

                failure_reason = (
                    f"description: {error_description}\n"
                    f"reason: {error_reason}\n"
                    f"source: {error_source}\n"
                    f"step: {error_step}"
                )

                payment_result = await db.execute(
                    update(Payment)
                    .where(
                        Payment.id == payment_record.id,
                        Payment.status.in_([
                            PaymentStatus.CREATED,
                            PaymentStatus.PROCESSING
                        ])
                    )
                    .values(
                        status=PaymentStatus.FAILED,
                        gateway_error_code=error_code,
                        failure_reason=failure_reason
                    )
                )

                if payment_result.rowcount == 0:
                    await db.rollback()

                    raise HTTPException(
                        status_code=409,
                        detail="Payment state changed during processing"
                    )

                if participation_type == "SINGLE":

                    registration_result = await db.execute(
                        update(SingleRegistration)
                        .where(
                            SingleRegistration.user_id == user_id,
                            SingleRegistration.event_id == event_id,
                            SingleRegistration.id == participation_id,
                        )
                        .values(
                            status=SingleRegistrationStatus.CANCELLED,
                            payment_status=SingleRegistrationPaymentStatus.FAILED,
                        )
                    )

                elif participation_type == "TEAM":

                    registration_result = await db.execute(
                        update(TeamRegistration)
                        .where(
                            TeamRegistration.captain_id == user_id,
                            TeamRegistration.event_id == event_id,
                            TeamRegistration.id == participation_id,
                        )
                        .values(
                            status=TeamRegistrationStatus.CANCELLED,
                            payment_status=TeamRegistrationPaymentStatus.FAILED,
                        )
                    )

                else:
                    await db.rollback()
                    logger.warning(f"Invalid participation type: {participation_type}")

                    raise HTTPException(status_code=400,detail="Invalid participation type")

                if registration_result.rowcount == 0:
                    await db.rollback()

                    logger.warning(
                        f"No registration updated. "
                        f"event={event}, "
                        f"type={participation_type}, "
                        f"id={participation_id}"
                    )

                    raise HTTPException(status_code=404,detail="Registration not found")

            elif current_status == PaymentStatus.SUCCESS:
                logger.warning(
                    f"Ignoring failed webhook because payment is already "
                    f"SUCCESS: {payment_id}"
                )

            elif current_status == PaymentStatus.FAILED:
                logger.info(f"Payment already FAILED: {payment_id}")

            new_webhook_event.processed = True
            new_webhook_event.processed_at = auth_util.get_now_utc()
            await db.commit()

        except HTTPException:
            raise

        except Exception:
            await db.rollback()

            logger.exception(f"Failed processing payment.failed webhook: {webhook_event_id}")

            raise HTTPException(status_code=500,detail="Webhook processing failed")

        finally:
            await release_payment_lock(lock_key,lock_token)

    else:
        logger.info(f"Received unsupported Razorpay webhook event: {event}")

        new_webhook_event.processed = True
        new_webhook_event.processed_at = auth_util.get_now_utc()

        try:
            await db.commit()

        except Exception:
            await db.rollback()

            logger.exception(f"Failed to commit unsupported webhook: {webhook_event_id}")

            raise HTTPException(status_code=500,detail="Webhook processing failed")

    logger.info(
        "Razorpay webhook processed",
        extra={
            "webhook_event_id": webhook_event_id,
            "event": event,
            "payment_id": payment_id,
            "order_id": order_id,
            "payment_status": payment_status,
            "event_id": event_id,
            "participation_type": participation_type,
            "participation_id": participation_id,
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "method": method,
        },
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Webhook processed successfully",
            "data": None,
            "error": None
        }
    )