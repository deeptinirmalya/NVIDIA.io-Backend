import base64
import uuid
import httpx
import logging
import binascii
import secrets
import json
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select, cast, String

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

from db.models.payment import(
    Payment,
    PaymentParticipationType,
    PaymentStatus
)

from db.session import get_db
# from security import auth as security
from engine.cache import redis_client
from security.rate_limiter import rate_limiter
from security.auth import get_client_info, token_required
from utils import auth_util, util
from templates import email_templates 
from engine.cache import get_value, set_value, delete_value


from services.razorpay_client import razorpay_client
from services.registration_service import RegistrationService



from .schemas import EventCreate, EventResponse
from core.config import settings
from monitoring.posthog import posthog

logger = logging.getLogger("event")

event_router = APIRouter()




ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
}

MAX_IMAGE_SIZE = 3 * 1024 * 1024 

def validate_banner(base64_image: str):
    try:
        if not base64_image.startswith("data:image/"):
            raise HTTPException(status_code=400, detail="Invalid image format")

        header, encoded_data = base64_image.split(",", 1)


        mime_type = header.split(";")[0].replace("data:", "")

        if mime_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only PNG, JPG and JPEG images are allowed")

        image_bytes = base64.b64decode(
            encoded_data,
            validate=True
        )

        # Validate size
        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400,detail="Image size must not exceed 10 MB")

        return True

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Base64 image format")

    except binascii.Error:
        raise HTTPException(status_code=400, detail="Invalid Base64 image data")



#add token required 
@event_router.post("/add-event")
async def create_event(
    event_data: EventCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(rate_limiter(max_tokens=5, refill_rate=0.25, mode="both"))
):
    try:
        existing_event = await db.scalar(select(Event).where(Event.name == event_data.name))

        if existing_event is not None:
            logger.warning("Event With this name already exists", extra={"event_name": event_data.name})
            raise HTTPException(status_code=409, detail="An event with this name already exists")

        validate_banner(event_data.banner)

        image_name = str(secrets.randbelow(9000000000000000) + 1000000000000000)


        result = util.cloudinary.uploader.upload(
            event_data.banner,
            public_id=image_name,
            resource_type="image"
        )

        banner_url = result["secure_url"]


        event_values = event_data.model_dump(exclude={"banner"})

        new_event = Event(**event_values, banner_url=banner_url, created_at=auth_util.get_now_utc())

        db.add(new_event)
        await db.commit()

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "event creation successful",
                "data": None,
                "error": None
            }
        )

    except HTTPException as httpe:
        await db.rollback()
        raise httpe

    except Exception as e:
        await db.rollback()
        logger.exception("exception during event creation", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Unable to create event")



@event_router.get("/catalogs")
async def view_events(
    db: AsyncSession = Depends(get_db),
):
    cache_key = "all_events:summary"

    try:
        cached = await get_value(cache_key)

        if cached is not None:
            return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Events retrieved successfully",
                        "data": cached,
                        "error": None,
                    }
                )

        events_query = (
            select(
                Event.id,
                Event.name,
                cast(Event.category, String).label("category"),
                cast(Event.gender_type, String).label("gender_type"),
                cast(Event.participation_type, String).label("participation_type"),
                Event.banner_url
                )
            .where(Event.status != EventStatus.DRAFT)
            .order_by(Event.created_at.desc(), Event.id.desc()))

        result = await db.execute(events_query)

        events_data = list(map(dict, result.mappings().all(),))
        
        await set_value(cache_key, events_data, expire=7200)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Events retrieved successfully",
                "data": events_data,
                "error": None,
            }
        )

    except Exception:
        logger.exception("Error while retrieving events")
        raise HTTPException(status_code=500, detail="Failed to retrieve events")




@event_router.get("/view/{event_id}/details")
async def get_event_details(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    # user_id: dict = Depends(token_required(allowed_roles=["STUDENT", "ADMIN", "SUPERADMIN"])),
    _= Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
):
    cache_key = f"event_{event_id}_details"
    try:
        data = await get_value(cache_key)

        if not data or data is None:
            stmt = select(Event).where(Event.id == event_id, Event.status != EventStatus.DRAFT)
            event_result = (await db.execute(stmt)).scalar_one_or_none()

            if not event_result or event_result is None:
                logger.warning(f"no event found for id {event_id}")
                raise HTTPException(status_code=404, detail="No event found")

            event_details = EventResponse.model_validate(event_result).model_dump(mode="json")
            
            await set_value(cache_key, event_details, expire=3600)

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Event details",
                    "data": event_details,
                    "error": None
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event details",
                "data": data,
                "error": None
            }
        )

    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("Errror during fatching event details", extra={"event_id": event_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Faild to load event details")



@event_router.post("/participate/{event_id}/single-event")
async def participate_on_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.2, mode="user")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    user_id = 1  # for demo; replace with token user id later

    try:
        # 1. Check event availability
        event_details = await RegistrationService.check_single_event_availability_for_participation(db, event_id, user_id)

        if not event_details["data"].get("is_paid"):  # free event
            # check or create registration and return its response
            return await RegistrationService.check_or_create_single_free_registration(db, event_id, user_id)

        else:  # paid event

            if not idempotency_key:
                raise HTTPException(status_code=400, detail="Idempotency-Key header is required for paid events")

            entry_result = await RegistrationService.check_or_create_single_paid_registration(
                db,
                event_id,
                user_id,
                idempotency_key
            )


            if isinstance(entry_result, JSONResponse):
                return entry_result

            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "Payment created",
                    "data": {
                        "order_id": entry_result["order_id"],
                        "razor_pay_key_id": settings.RAZORPAY_KEY_ID
                    },
                    "error": None
                }
            )
        





    except HTTPException as httpe:
        
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("Failsd to participate in event", extra={"event_id": event_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Faild to participate in event")
