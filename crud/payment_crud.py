import asyncio
import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select, cast, String, update


from db.models.single_registration import(
    SingleRegistrationStatus,
    SingleRegistrationPaymentStatus,
    SingleRegistration
)

from db.models.payment import(
    Payment,
    PaymentParticipationType,
    PaymentStatus,
    FirstCame
)

from db.models.team_registration import(
    TeamRegistration,
    TeamRegistrationStatus,
    TeamRegistrationPaymentStatus
)

from db.models.event import (Event)

from utils import util, auth_util
from services.razorpay_client import razorpay_client, create_razorpay_order

from core.config import settings


logger = logging.getLogger("payment_crud")

class PaymentCrudServices:

    @staticmethod
    async def initialize_single_starter_payment_entry(
        db: AsyncSession,
        event_id: int,
        user_id: int,
        participation_id: int,
        idempotenci_key: str,
    ):
        try:
            # Select the full Event row so .price is accessible
            stmt = select(Event).where(Event.id == event_id)
            event_details = (await db.execute(stmt)).scalar_one_or_none()

            # Guard: event could have been deleted between availability check and here
            if event_details is None:
                raise HTTPException(status_code=404, detail="Event no longer available")

            new_starter_entry = Payment(
                participation_type=PaymentParticipationType.SINGLE,
                single_registration_id=participation_id,
                amount=event_details.price,
                idempotency_key=idempotenci_key,
                created_at=auth_util.get_now_utc()
            )
            db.add(new_starter_entry)
            await db.flush()

            # Persist the local attempt before making the external gateway call.
            # This prevents a failed local commit from leaving an orphaned Razorpay order.
            await db.commit()


            # The Razorpay HTTP client is asynchronous, so await the order response.
            try:
                order = await create_razorpay_order(
                    event_details.price,
                    participation_id,
                    "SINGLE",
                    event_id,
                    user_id,
                )
                order_id = order.get("id")
                if not order_id:
                    raise RuntimeError("Razorpay returned an order without an id")
            except Exception as gateway_error:
                await db.rollback()
                await db.execute(
                    update(Payment)
                    .where(Payment.id == new_starter_entry.id)
                    .values(
                        status=PaymentStatus.FAILED,
                        failure_reason="Razorpay order creation failed",
                        updated_at=auth_util.get_now_utc(),
                    )
                )
                await db.execute(
                    update(SingleRegistration)
                    .where(SingleRegistration.id == participation_id)
                    .values(
                        status=SingleRegistrationStatus.CANCELLED,
                        payment_status=SingleRegistrationPaymentStatus.FAILED,
                        updated_at=auth_util.get_now_utc(),
                    )
                )
                await db.commit()
                logger.exception(
                    "Razorpay order creation failed",
                    extra={"event_id": event_id, "user_id": user_id},
                )
                raise HTTPException(
                    status_code=502,
                    detail="Unable to initialize payment",
                ) from gateway_error

            update_stmt = (
                update(Payment)
                .where(Payment.id == new_starter_entry.id)
                .values(
                    razorpay_order_id=order_id,
                    updated_at=auth_util.get_now_utc(),
                )
            )
            await db.execute(update_stmt)

            await db.commit()
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "created",
                    "data":{"order_id": order_id, "key_id": settings.RAZORPAY_KEY_ID},
                    "error": None
                }
            )

        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in PaymentCrudServices – initialize_single_starter_payment_entry", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")



    @staticmethod
    async def initialize_team_starter_payment_entry(
        db: AsyncSession,
        event_id: int,
        user_id: int,
        participation_id: int,
        idempotenci_key: str,
    ):
        try:
            # Select the full Event row so .price is accessible
            stmt = select(Event).where(Event.id == event_id)
            event_details = (await db.execute(stmt)).scalar_one_or_none()

            # Guard: event could have been deleted between availability check and here
            if event_details is None:
                raise HTTPException(status_code=404, detail="Event no longer available")

            new_starter_entry = Payment(
                participation_type=PaymentParticipationType.TEAM,
                team_registration_id=participation_id,
                amount=event_details.price,
                idempotency_key=idempotenci_key,
                created_at=auth_util.get_now_utc()
            )
            db.add(new_starter_entry)
            await db.flush()

            # Persist the local attempt before making the external gateway call.
            # This prevents a failed local commit from leaving an orphaned Razorpay order.
            await db.commit()


            # The Razorpay HTTP client is asynchronous, so await the order response.
            try:
                order = await create_razorpay_order(
                    event_details.price,
                    participation_id,
                    "TEAM",
                    event_id,
                    user_id,
                )
                order_id = order.get("id")
                if not order_id:
                    raise RuntimeError("Razorpay returned an order without an id")
            except Exception as gateway_error:
                await db.rollback()
                await db.execute(
                    update(Payment)
                    .where(Payment.id == new_starter_entry.id)
                    .values(
                        status=PaymentStatus.FAILED,
                        failure_reason="Razorpay order creation failed",
                        updated_at=auth_util.get_now_utc(),
                    )
                )
                await db.execute(
                    update(TeamRegistration)
                    .where(TeamRegistration.id == participation_id)
                    .values(
                        status=TeamRegistrationStatus.CANCELLED,
                        payment_status=TeamRegistrationPaymentStatus.FAILED,
                        updated_at=auth_util.get_now_utc(),
                    )
                )
                await db.commit()
                logger.exception("Razorpay order creation failed at initialize_team_starter_payment_entry",extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=502,detail="Unable to initialize payment") #from gateway_error

            update_stmt = (
                update(Payment)
                .where(Payment.id == new_starter_entry.id)
                .values(
                    razorpay_order_id=order_id,
                    updated_at=auth_util.get_now_utc(),
                )
            )
            await db.execute(update_stmt)

            await db.commit()
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "created",
                    "data":{"order_id": order_id, "key_id": settings.RAZORPAY_KEY_ID},
                    "error": None
                }
            )

        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in PaymentCrudServices – initialize_single_starter_payment_entry", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")

    @staticmethod
    async def update_transactin_to_processing(db: AsyncSession, db_result, data, user_id, participation_type):
        if participation_type == "SINGLE":
            secret_code = util.encode_dict({
                "registration_id": db_result.single_registration_id,
                "participation_type":"SINGLE"
            }, settings.ENCRYPTION_KEY)
        else:
            secret_code = util.encode_dict({
                "registration_id": db_result.team_registration_id,
                "participation_type":"TEAM"
            }, settings.ENCRYPTION_KEY)
        try:
            db_result.status = PaymentStatus.PROCESSING
            db_result.razorpay_payment_id = data.razorpay_payment_id
            db_result.razorpay_signature = data.razorpay_signature
            db_result.first_came = FirstCame.FRONTEND
            db_result.signature_verified = True

            await db.commit()
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "payment is under proccessing",
                    "data":secret_code,
                    "error": None
                }
            )
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in PaymentCrudServices – update_transactin_to_processing", extra={"user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Internal server Error")