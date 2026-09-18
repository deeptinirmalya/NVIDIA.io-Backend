import razorpay
import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, exists, func, or_, select, cast, String

from db.models.payment import(
    Payment,
    PaymentParticipationType,
    PaymentStatus
)
from db.models.single_registration import SingleRegistration
from db.models.team_member import TeamMember
from db.models.team_registration import TeamRegistration

from crud.payment_crud import PaymentCrudServices
from services.razorpay_client import razorpay_client

from engine.cache import acquire_payment_lock, release_payment_lock
from core.config import settings
from utils import util


logger = logging.getLogger("payment_service")

def verify_razorpay_signature_sdk(params_dict: dict) -> bool:
    """ Verify Razorpay payment signature using the Razorpay SDK. 
    params_dict must contain: - 
    razorpay_order_id - 
    razorpay_payment_id - 
    razorpay_signature 
    """ 
    try: 
        razorpay_client.utility.verify_payment_signature(params_dict)
        return True 
    except razorpay.SignatureVerificationError: 
        return False

class PaymentServices:

    @staticmethod
    async def check_idempotency_key_for_singel_event(
        db: AsyncSession, 
        idempotency_key: str,
        event_id: int,
        user_id: int
        ):
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise HTTPException(status_code=422, detail="Idempotency-Key must not be empty")

        if len(idempotency_key) > 100:
            raise HTTPException(status_code=422, detail="Idempotency-Key must not exceed 100 characters")

        scoped_stmt = (
            select(Payment)
            .join(
                SingleRegistration,
                Payment.single_registration_id == SingleRegistration.id,
            )
            .where(
                Payment.idempotency_key == idempotency_key,
                SingleRegistration.user_id == user_id,
                SingleRegistration.event_id == event_id,
            )
        )
        existing_idempotency_key_value = (await db.execute(scoped_stmt)).scalar_one_or_none()

        if existing_idempotency_key_value is None:
            conflicting_key_stmt = select(Payment.id).where(
                Payment.idempotency_key == idempotency_key
            )
            conflicting_payment_id = (await db.execute(conflicting_key_stmt)).scalar_one_or_none()
            if conflicting_payment_id is not None:
                raise HTTPException(status_code=409, detail="Idempotency key already used")

        if existing_idempotency_key_value:

            logger.warning("idempotency key re hit", extra={"event_id": event_id, "user_id": user_id})

            if existing_idempotency_key_value.status == PaymentStatus.SUCCESS:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Payment already completed",
                        "data": {
                            "payment_id": existing_idempotency_key_value.id,
                            "status": existing_idempotency_key_value.status.value
                        },
                        "error": None
                    }
                )

            if existing_idempotency_key_value.status in [PaymentStatus.CREATED, PaymentStatus.PROCESSING]:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Payment is under processing or created",
                        "data": {
                            "payment_id": existing_idempotency_key_value.id,
                            "razorpay_order_id": existing_idempotency_key_value.razorpay_order_id,
                            "amount": existing_idempotency_key_value.amount,
                            "currency": existing_idempotency_key_value.currency,
                            "status": existing_idempotency_key_value.status.value,
                            "key_id": settings.RAZORPAY_KEY_ID
                        },
                        "error": None
                    }
                )

            if existing_idempotency_key_value.status == PaymentStatus.FAILED:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Previous payment failed. Create a new payment attempt.",
                        "data": {
                            "payment_id": existing_idempotency_key_value.id,
                            "status": existing_idempotency_key_value.status.value
                        },
                        "error": None
                    }
                )

        # No existing key — caller may proceed to create a new payment
        return None


    @staticmethod
    async def check_idempotency_key_for_team_event(
        db: AsyncSession, 
        idempotency_key: str,
        event_id: int,
        user_id: int
        ):
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise HTTPException(status_code=422, detail="Idempotency-Key must not be empty")

        if len(idempotency_key) > 100:
            raise HTTPException(status_code=422, detail="Idempotency-Key must not exceed 100 characters")

        scoped_stmt = (
            select(Payment)
            .join(
                TeamRegistration,
                Payment.team_registration_id == TeamRegistration.id,
            )
            .where(
                Payment.idempotency_key == idempotency_key,
                TeamRegistration.captain_id == user_id,
                TeamRegistration.event_id == event_id,
            )
        )
        existing_idempotency_key_value = (await db.execute(scoped_stmt)).scalar_one_or_none()

        if existing_idempotency_key_value is None:
            conflicting_key_stmt = select(Payment.id).where(
                Payment.idempotency_key == idempotency_key
            )
            conflicting_payment_id = (await db.execute(conflicting_key_stmt)).scalar_one_or_none()
            if conflicting_payment_id is not None:
                raise HTTPException(status_code=409, detail="Idempotency key already used")

        if existing_idempotency_key_value:

            logger.warning("idempotency key re hit", extra={"event_id": event_id, "user_id": user_id})

            if existing_idempotency_key_value.status == PaymentStatus.SUCCESS:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Payment already completed",
                        "data": {
                            "payment_id": existing_idempotency_key_value.id,
                            "status": existing_idempotency_key_value.status.value
                        },
                        "error": None
                    }
                )

            if existing_idempotency_key_value.status in [PaymentStatus.CREATED, PaymentStatus.PROCESSING]:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Payment is under processing or created",
                        "data": {
                            "payment_id": existing_idempotency_key_value.id,
                            "razorpay_order_id": existing_idempotency_key_value.razorpay_order_id,
                            "amount": existing_idempotency_key_value.amount,
                            "currency": existing_idempotency_key_value.currency,
                            "status": existing_idempotency_key_value.status.value,
                            "key_id": settings.RAZORPAY_KEY_ID
                        },
                        "error": None
                    }
                )

            if existing_idempotency_key_value.status == PaymentStatus.FAILED:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Previous payment failed. Create a new payment attempt.",
                        "data": {
                            "payment_id": existing_idempotency_key_value.id,
                            "status": existing_idempotency_key_value.status.value
                        },
                        "error": None
                    }
                )

        # No existing key — caller may proceed to create a new payment
        return None


    @staticmethod
    async def verify_payment_request_by_frontend(db: AsyncSession, data, user_id: int):
        try:
            stmt = select(Payment).where(
                Payment.razorpay_order_id == data.razorpay_order_id
            )

            db_result = (await db.execute(stmt)).scalar_one_or_none()

            if db_result is None:
                logger.warning("payment not found in verify_payment_request_by_frontend",extra={"user_id": user_id})
                raise HTTPException(status_code=404,detail="No transaction found with that order id")

            # Check association
            if db_result.participation_type == PaymentParticipationType.SINGLE:
                stmt_single = (
                    await db.execute(
                        select(SingleRegistration.id).where(
                            SingleRegistration.id == db_result.single_registration_id,
                            SingleRegistration.user_id == user_id
                        )
                    )
                ).scalar_one_or_none()

                if stmt_single is None:
                    logger.warning("try unauthorize request for order id",extra={"user_id": user_id})
                    raise HTTPException(status_code=409,detail="Unauthorize")

            if db_result.participation_type == PaymentParticipationType.TEAM:
                stmt_team = (
                    await db.execute(
                        select(TeamRegistration.id).where(
                            TeamRegistration.id == db_result.team_registration_id,
                            TeamRegistration.captain_id == user_id
                        )
                    )
                ).scalar_one_or_none()

                if stmt_team is None:
                    logger.warning("try unauthorize request for order id",extra={"user_id": user_id})
                    raise HTTPException(status_code=409,detail="Unauthorize")

            # Verify Razorpay frontend signature
            is_signature_verified = verify_razorpay_signature_sdk({
                "razorpay_order_id": data.razorpay_order_id,
                "razorpay_payment_id": data.razorpay_payment_id,
                "razorpay_signature": data.razorpay_signature
            })

            if not is_signature_verified:
                logger.warning("signature not verified during verify_payment_request_by_frontend", extra={"data": data, "user_id": user_id})
                raise HTTPException(status_code=409,detail="Signature not verified")

            lock_token, lock_key = await acquire_payment_lock(db_result.id)

            if lock_token is None:
                raise HTTPException(status_code=409,detail="Payment is currently being processed")

            try:
                await db.refresh(db_result)
                if db_result.status != PaymentStatus.CREATED:
                    db_result.razorpay_payment_id = data.razorpay_payment_id
                    db_result.razorpay_signature = data.razorpay_signature
                    db_result.signature_verified = True

                    await db.commit()

                    if db_result.participation_type == PaymentParticipationType.SINGLE:
                        secret_code = util.encode_dict(
                                                    {
                                                        "registration_id": db_result.single_registration_id,
                                                        "participation_type": "SINGLE"
                                                    },
                                                    settings.ENCRYPTION_KEY
                                                )
                    else:
                        secret_code = util.encode_dict(
                                                    {
                                                        "registration_id": db_result.team_registration_id,
                                                        "participation_type": "TEAM"
                                                    },
                                                    settings.ENCRYPTION_KEY
                                                )

                    # Do not treat FAILED as successfully processed.
                    if db_result.status == PaymentStatus.FAILED:
                        return JSONResponse(
                            status_code=200,
                            content={
                                "success": False,
                                "message": "Payment failed",
                                "data": secret_code,
                                "error": None
                            }
                        )

                    return JSONResponse(
                        status_code=200,
                        content={
                            "success": True,
                            "message": "data already processed",
                            "data": secret_code,
                            "error": None
                        }
                    )
                result = await PaymentCrudServices.update_transactin_to_processing(
                                                                                db,
                                                                                db_result,
                                                                                data,
                                                                                user_id,
                                                                                db_result.participation_type,
                                                                            )

                return result
            finally:
                await release_payment_lock(lock_key, lock_token)
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception(
                "exception during verify_payment_request_by_frontend",
                extra={
                    "data": data,
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise HTTPException(status_code=500,detail="Internal Server Error")
