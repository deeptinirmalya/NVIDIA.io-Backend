import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select, cast, String


from db.models.single_registration import(
    SingleRegistrationStatus,
    SingleRegistrationPaymentStatus,
    SingleRegistration
)

from utils import util, auth_util


logger = logging.getLogger("Single_registration_crud")

class SingleregistrationCrudService:

    # ======================== FOR  FREE EVENTS ===========================

    @staticmethod
    async def create_free_sigle_participation(
        db: AsyncSession,
        event_id: int,
        user_id: int
    ):
        try:
            new_free_registration = SingleRegistration(
                user_id = user_id,
                event_id = event_id,
                status = SingleRegistrationStatus.CONFIRMED,
                payment_status = SingleRegistrationPaymentStatus.NOT_REQUIRED,
                created_at = auth_util.get_now_utc()
            )
            db.add(new_free_registration)
            await db.commit()

            logger.info(f"User participate on  {event_id} free single", extra={"event_id": event_id, "user_id": user_id})

            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "participate success fully",
                    "data": None,
                    "error": None
                }
            )
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in SingleregistrationService – create_free_sigleparticipation", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")


    # ======================== FOR PAID EVENTS =================

    @staticmethod
    async def intialize_starter_paid_registration_entry(
        db: AsyncSession,
        event_id: int,
        user_id: int
    ):
        try:
            new_paid_registration = SingleRegistration(
                user_id = user_id,
                event_id = event_id,
                status = SingleRegistrationStatus.PENDING,
                payment_status = SingleRegistrationPaymentStatus.PENDING,
                created_at = auth_util.get_now_utc()
            )
            db.add(new_paid_registration)
            await db.flush()                          
            await db.refresh(new_paid_registration)   

            return new_paid_registration
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in SingleregistrationService – intialize_starter_paid_registration", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")