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
    PaymentStatus
)

from db.models.event import (Event)

from utils import util, auth_util
from services.razorpay_client import razorpay_client


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

            amount = event_details.price * 100
            # Razorpay SDK is synchronous — run in thread pool to avoid blocking the event loop
            order = await asyncio.to_thread(
                razorpay_client.order.create,
                {
                    "amount": amount,
                    "currency": "INR",
                    "receipt": f"single_participate_{participation_id}",
                    "notes": {
                        "participation_type": "SINGLE",
                        "participate_id": str(participation_id),
                        "event_id": str(event_id),
                        "user_id": str(user_id),
                    }
                }
            )
            update_stmt = (update(Payment).where(Payment.id == new_starter_entry.id).values(razorpay_order_id=order["id"]))
            await db.execute(update_stmt)

            await db.commit()

            return {
                "order_id": order["id"]
            }
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in PaymentCrudServices – initialize_single_starter_payment_entry", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")

    @staticmethod
    async def update_transactin_to_processing(db: AsyncSession, db_result, data, user_id, participation_type):
        if participation_type == "SINGLE":
            registration_id = db_result.single_registration_id
        else:
            registration_id = db_result.team_registration_id
        try:
            db_result.status = PaymentStatus.PROCESSING
            db_result.razorpay_payment_id = data.razorpay_payment_id
            db_result.razorpay_signature = data.razorpay_signature
            db_result.signature_verified = True

            await db.commit()
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "payment verified",
                    "data":{
                        "registration_id": registration_id,
                        "participation_type": participation_type
                    }
                }
            )
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in PaymentCrudServices – update_transactin_to_processing", extra={"user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Internal server Error")