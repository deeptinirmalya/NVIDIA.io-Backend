import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select, cast, String

from crud.single_registration_crud import SingleregistrationCrudService
from crud.payment_crud import PaymentCrudServices
from crud.team_registration_crud import TeamregistrationCrudService

from .payment_service import PaymentServices


from db.models.event import (
    Event,
    EventCategory,
    EventStatus,
    GenderType,
    ParticipationType
)

from db.models.single_registration import(
    SingleRegistrationStatus,
    SingleRegistrationPaymentStatus,
    SingleRegistration
)

from db.models.team_registration import(
    TeamRegistration,
    TeamRegistrationPaymentStatus,
    TeamRegistrationStatus
)

from utils import util, auth_util


logger = logging.getLogger("registration_service")



DISALLOWED_STATUSES = {"ONGOING", 
                        "COMPLETED", 
                        "CANCELLED", 
                        "REGISTRATION_CLOSED"
                        }

class RegistrationService:

    @staticmethod
    async def check_single_event_availability_for_participation(
            db: AsyncSession,
            event_id: int,
            user_id: int
        ):

        now = auth_util.get_now_ist()
        try:
            stmt = select(Event).where(Event.id == event_id, Event.status != EventStatus.DRAFT, Event.participation_type == ParticipationType.SINGLE)
            event_details = (await db.execute(stmt)).scalar_one_or_none()

            if event_details is None:
                logger.warning(f"Event not fount to participate {event_id}", extra={"event_id": event_id})
                raise HTTPException(status_code=404, detail="Event not found")

            if event_details.status.value in DISALLOWED_STATUSES:
                raise HTTPException(status_code=409, detail=f"Can't participate event has already {event_details.status.value.lower()}")


            if now < util.ensure_aware_ist(event_details.registration_start_time):
                logger.warning(f"Event registration not started {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Event registration not started")
            
            if now > util.ensure_aware_ist(event_details.registration_end_time):
                logger.warning(f"Event registration closed {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Event registration closed")

            return {
                "success": True,
                "data":{"is_paid": bool(event_details.is_paid)},
                "error": None
            }
        
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            logger.exception("Exception in registration service – check availability", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")

        
    @staticmethod
    async def check_team_event_availability_for_participation(
            db: AsyncSession,
            event_id: int,
            user_id: int
        ):

        now = auth_util.get_now_ist()
        try:
            stmt = select(Event).where(Event.id == event_id, Event.status != EventStatus.DRAFT, Event.participation_type == ParticipationType.TEAM)
            event_details = (await db.execute(stmt)).scalar_one_or_none()

            if event_details is None:
                logger.warning(f"Event not found to participate {event_id}", extra={"event_id": event_id})
                raise HTTPException(status_code=404, detail="Event not found")

            if event_details.status.value in DISALLOWED_STATUSES:
                raise HTTPException(status_code=409, detail=f"Can't participate, event has already {event_details.status.value.lower()}")


            if now < util.ensure_aware_ist(event_details.registration_start_time):
                logger.warning(f"Event registration not started {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Event registration not started")
            
            if now > util.ensure_aware_ist(event_details.registration_end_time):
                logger.warning(f"Event registration closed {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Event registration closed")

            return {
                "success": True,
                "data":{"is_paid": bool(event_details.is_paid)},
                "error": None
            }
        
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            logger.exception("Exception in registration service – check availability", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")


# ================================= FOR SINGLE+FREE EVENTS ================================
    @staticmethod
    async def check_or_create_single_free_registration(
        db: AsyncSession,
        event_id: int,
        user_id: int
    ):
        try:
            stmt = select(SingleRegistration.id).where(SingleRegistration.user_id == user_id, SingleRegistration.event_id == event_id)
            existing_result = (await db.execute(stmt)).scalar_one_or_none()
            if existing_result is not None:
                logger.warning(f"User already participate on  {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Already participated")

            return await SingleregistrationCrudService.create_free_sigle_participation(db, event_id, user_id)
            
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            logger.exception("Exception in registration service – check_user_single_free_registration", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")



# ================================= FOR SINGLE+PAID EVENTS ================================

    @staticmethod
    async def check_or_create_single_paid_registration(
        db: AsyncSession,
        event_id: int,
        user_id: int,
        idempotency_key: str
    ):
        try:
            # Resolve retries before rejecting the existing pending registration.
            idempotency_response = await PaymentServices.check_idempotency_key_for_singel_event(
                db, idempotency_key, event_id, user_id
            )
            if idempotency_response is not None:
                return idempotency_response

            # Reject a new payment attempt when the user already has a registration.
            stmt = (select(SingleRegistration.id)
                    .where(
                        SingleRegistration.user_id == user_id,
                        SingleRegistration.event_id == event_id,
                        SingleRegistration.status.in_([
                            SingleRegistrationStatus.CONFIRMED,
                            SingleRegistrationStatus.PENDING
                        ])
                        ))
            existing_result = (await db.execute(stmt)).scalar_one_or_none()
            if existing_result is not None:
                logger.warning(f"User already participate on  {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Already participated")

            entry_result = await SingleregistrationCrudService.intialize_starter_paid_registration_entry(db, event_id, user_id)

            next_result = await PaymentCrudServices.initialize_single_starter_payment_entry(db, event_id, user_id, entry_result.id, idempotency_key)

            return next_result
            
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in registration service – check_user_single_paid_registration", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")



# ============================ FOR TEAM+FREE EVENTS ========================================

    @staticmethod
    async def check_or_create_team_free_registration(
        db: AsyncSession,
        event_id: int,
        user_id: int,
        team_name: str
    ):
        try:
            stmt = select(TeamRegistration.id).where(TeamRegistration.captain_id == user_id, TeamRegistration.event_id == event_id)
            existing_result = (await db.execute(stmt)).scalar_one_or_none()
            if existing_result is not None:
                logger.warning(f"User already participate on  {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Already participated")
            
            return await TeamregistrationCrudService.create_free_team_participation(db, event_id, user_id, team_name)
            
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            logger.exception("Exception in registration service – check_user_single_free_registration", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")

# ================================= FOR TEAM+PAID EVENTS ================================

    @staticmethod
    async def check_or_create_team_paid_registration(
        db: AsyncSession,
        event_id: int,
        user_id: int,
        idempotency_key: str,
        team_name: str
    ):
        try:
            # Resolve retries before rejecting the existing pending registration.
            idempotency_response = await PaymentServices.check_idempotency_key_for_team_event(
                db, idempotency_key, event_id, user_id
            )
            if idempotency_response is not None:
                return idempotency_response

            # Reject a new payment attempt when the user already has a registration.
            stmt = (select(TeamRegistration.id)
                    .where(
                        TeamRegistration.captain_id == user_id,
                        TeamRegistration.event_id == event_id,
                        TeamRegistration.status.in_([
                            TeamRegistrationStatus.CONFIRMED,
                            TeamRegistrationStatus.PENDING
                        ])
                        ))
            existing_result = (await db.execute(stmt)).scalar_one_or_none()
            if existing_result is not None:
                logger.warning(f"User already participate on  {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Already participated")

            entry_result = await TeamregistrationCrudService.intialize_starter_paid_registration_entry(db, event_id, user_id, team_name)

            next_result = await PaymentCrudServices.initialize_team_starter_payment_entry(db, event_id, user_id, entry_result.id, idempotency_key)

            return next_result
            
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in registration service – check_user_single_paid_registration", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")


