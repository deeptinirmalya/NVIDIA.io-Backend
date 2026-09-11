import razorpay
import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select, cast, String

from db.models.payment import(
    Payment,
    PaymentParticipationType,
    PaymentStatus
)

from crud.payment_crud import PaymentCrudServices
from services.razorpay_client import razorpay_client

from core.config import settings


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
    async def check_idempotency_key(
        db: AsyncSession, 
        ideampotency_key: str,
        event_id: int,
        user_id: int
        ):

        ideampotency_stmt = select(Payment).where(Payment.idempotency_key == ideampotency_key)
        existing_idempotency_key_value = (await db.execute(ideampotency_stmt)).scalar_one_or_none()

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
            
            stmt = select(Payment).where(Payment.razorpay_order_id == data.razorpay_order_id)
            db_result = (await db.execute(stmt)).scalar_one_or_none()
            if db_result is None:
                logger.exception("no transaction found with order id", extra={"razorpay_order_id": data.razorpay_order_id, "user_id": user_id})
                raise HTTPException(status_code=404, detail="No transaction found with that order id")

            is_signature_verified = verify_razorpay_signature_sdk({
                "razorpay_order_id": data.razorpay_order_id,
                "razorpay_payment_id": data.razorpay_payment_id,
                "razorpay_signature": data.razorpay_signature
                })
            if not is_signature_verified:
                logger.exception(" signature not verified during verify_payment_request_by_frontend", extra={"data": data, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Signature not verified")

            result = await PaymentCrudServices.update_transactin_to_processing(
                                                                            db,
                                                                            db_result,
                                                                            data,
                                                                            user_id,
                                                                            db_result.participation_type,
                                                                        )
            return result

        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("exception during verify_payment_request_by_frontend", extra={"data": data, "user_id": user_id, "error": str(e)})
