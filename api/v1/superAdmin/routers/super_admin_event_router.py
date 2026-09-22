import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse
import binascii
import base64
import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, asc

from db.session import get_db
from security.auth import token_required
from security.rate_limiter import rate_limiter
from utils import auth_util, util


from ..schemas import EventCreate
from core.config import settings
from monitoring.posthog import posthog

from db.models.event import (
    Event,
    EventCategory,
    EventStatus
)


logger = logging.getLogger("Super-admin-Event")


superadmin_event_router = APIRouter()


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
@superadmin_event_router.post("/add-event")
async def create_event(
    event_data: EventCreate,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
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