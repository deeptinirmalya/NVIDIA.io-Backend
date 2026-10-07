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


from ..schemas import EventAdminResponse, EventCreate, EventUpdate, EventResponse
from core.config import settings
from monitoring.posthog import posthog
from engine.cache import delete_value
from engine.bloomfilter import add_event_id_to_bloom
from db.models.auth import(
    User,
    UserRole,
    UserStatus,
    Profile,
)

from db.models.event import(
    Event,
    EventStatus,
    ParticipationType,
)

from db.models.single_registration import(
    SingleRegistration,
    SingleRegistrationPaymentStatus,
    SingleRegistrationStatus
)

from db.models.team_registration import(
    TeamRegistration,
    TeamRegistrationStatus,
    TeamRegistrationPaymentStatus,
    TeamStatus
)
from db.models.team_member import TeamMember

from services.auditlog_service import create_audit_log
from services.count_service import increase_event_count

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

@superadmin_event_router.get("/view/{event_id:int}/details")
async def get_event_details(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _= Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
):
    try:

        stmt = select(Event).where(Event.id == event_id)
        event_result = (await db.execute(stmt)).scalar_one_or_none()

        if not event_result or event_result is None:
            logger.warning(f"no event found for id {event_id}")
            raise HTTPException(status_code=404, detail="No event found")

        event_details = EventResponse.model_validate(event_result).model_dump(mode="json")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event details",
                "data": event_details,
                "error": None
            }
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("Errror during fatching event details", extra={"event_id": event_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Faild to load event details")


@superadmin_event_router.post("/add-event")
async def create_event(
    event_data: EventCreate,
    request: Request,
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
        await db.refresh(new_event)

        await increase_event_count(
            db,
            event_type=event_data.participation_type.value.lower(),
            is_paid=event_data.is_paid,
        )
        await add_event_id_to_bloom(new_event.id)
        await delete_value("all_events:summary")

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="EVENT_ADDED",
            entity_type="EVENT",
            entity_id=None,
            description="Event status added by superadmin",
            metadata={
                "new_status": event_data.model_dump(mode="json", exclude={"banner"}),
            },
        )

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


@superadmin_event_router.get("/{event_id:int}")
async def get_event_for_editing(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _=Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    try:
        event = await db.scalar(select(Event).where(Event.id == event_id))
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        event_details = EventAdminResponse.model_validate(event).model_dump(mode="json")
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event details retrieved successfully",
                "data": event_details,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as exc:
        logger.exception("Exception while retrieving event details", extra={"event_id": event_id, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Unable to retrieve event details")


@superadmin_event_router.put("/update-event/{event_id:int}")
async def update_event(
    event_id: int,
    request: Request,
    event_data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _=Depends(rate_limiter(max_tokens=5, refill_rate=0.25, mode="both")),
):
    try:
        event = await db.scalar(select(Event).where(Event.id == event_id))
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        update_values = event_data.model_dump(exclude_unset=True)
        new_banner = update_values.pop("banner", None)

        if "name" in update_values:
            duplicate = await db.scalar(
                select(Event).where(Event.name == update_values["name"], Event.id != event_id)
            )
            if duplicate is not None:
                raise HTTPException(status_code=409, detail="An event with this name already exists")

        current_values = {
            field: getattr(event, field)
            for field in EventCreate.model_fields
            if field != "banner"
        }
        current_values.update(update_values)
        current_values["banner"] = new_banner or event.banner_url or "existing-banner"
        validated_values = EventCreate.model_validate(current_values).model_dump(exclude={"banner"})

        if new_banner is not None:
            validate_banner(new_banner)
            image_name = str(secrets.randbelow(9000000000000000) + 1000000000000000)
            result = util.cloudinary.uploader.upload(
                new_banner,
                public_id=image_name,
                resource_type="image",
            )
            validated_values["banner_url"] = result["secure_url"]

        for field, value in validated_values.items():
            setattr(event, field, value)
        event.updated_at = auth_util.get_now_utc()

        await db.commit()
        await db.refresh(event)
        await delete_value("all_events:summary")
        await delete_value(f"event_{event_id}_details")

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="EVENT_UPDATE",
            entity_type="EVENT",
            entity_id=event_id,
            description="Event updated by superadmin",
            metadata={
                "new_status": event_data.model_dump(mode="json", exclude={"banner"}),
            },
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event updated successfully",
                "data": {"id": event.id},
                "error": None,
            },
        )
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as exc:
        await db.rollback()
        logger.exception("Exception during event update", extra={"event_id": event_id, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Unable to update event")


@superadmin_event_router.patch("/update-event-status/{event_id:int}/{status}")
async def update_event_status(
    event_id: int,
    status: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=7, refill_rate=0.5, mode="both"))
):
    user_id = user_data["user_id"]
    normalized_status = status.upper()
    valid_statuses = {EventStatus.DRAFT, EventStatus.PUBLISHED, EventStatus.CANCELLED, EventStatus.COMPLETED, EventStatus.ONGOING, EventStatus.REGISTRATION_CLOSED}

    if normalized_status not in valid_statuses:
        logger.warning("invalid status type in status update", extra={"admin_id": user_id})
        raise HTTPException(status_code=422, detail="Invalid Status Type")

    try:
        result = await db.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(status=EventStatus(normalized_status))
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="No event found")

        await delete_value("all_events:summary")
        await delete_value(f"event_{event_id}_details")

        await db.commit()

        await create_audit_log(
            request=request,
            user_id=user_id,
            action="UPDATE_STATUS",
            entity_type="EVENT",
            entity_id=event_id,
            description="Event status updated by admin",
            metadata={
                "new_status": normalized_status,
            },
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event updated successfully",
                "data": None,
                "error": None,
            },
        )

    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception(
            "exception during event status update",
            extra={"admin_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@superadmin_event_router.get("/all-events")
async def get_all_events(
    search: str | None = Query(default=None, max_length=100, description="name of the event"),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(15, ge=1, le=15, description="Events per page"),
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    user_id = user_data["user_id"]
    # user_id = 1
    try:
        search_term = search.strip() if search else ""
        offset = (page - 1) * limit

        stmt = select(
            Event.id.label("event_id"),
            Event.name.label("event_name"),
            Event.category.label("event_category"),
            Event.registration_end_time.label("event_registration_close_time"),
            Event.event_start_time.label("event_start_time"),
            Event.participation_type.label("event_participation_type"),
            Event.status.label("event_status"),
        ).order_by(asc(Event.id))

        if search_term:
            stmt = stmt.where(Event.name.ilike(f"%{search_term}%"))

        stmt = stmt.offset(offset).limit(limit)

        result = await db.execute(stmt)
        events = []
        for row in result.mappings().all():
            event_dict = dict(row)
            if event_dict.get("event_registration_close_time"):
                event_dict["event_registration_close_time"] = event_dict["event_registration_close_time"].isoformat()
            if event_dict.get("event_start_time"):
                event_dict["event_start_time"] = event_dict["event_start_time"].isoformat()
            events.append(event_dict)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Events retrieved successfully",
                "data": events,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during events fetch by admin",
            extra={"admin_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@superadmin_event_router.get("/all-events-id")
async def get_all_events_id(
    search: str | None = Query(default=None, max_length=100, description="name of the event"),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(20, ge=1, le=20, description="Events per page"),
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    user_id = user_data["user_id"]
    # user_id = 1
    try:
        search_term = search.strip() if search else ""
        offset = (page - 1) * limit

        stmt = select(
            Event.id.label("event_id"),
            Event.name.label("event_name"),
            Event.participation_type.label("participation_type"),
        ).order_by(asc(Event.id))
        

        if search_term:
            stmt = stmt.where(Event.name.ilike(f"%{search_term}%"))

        stmt = stmt.offset(offset).limit(limit)

        result = await db.execute(stmt)
        events = [dict(row) for row in result.mappings().all()]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Events retrieved successfully",
                "data": events,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during event id fetch by admin",
            extra={"admin_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")



@superadmin_event_router.get("/event-registrations/{event_id}")
async def get_event_registrations(
    event_id: int,
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(15, ge=1, le=15, description="Registrations per page"),
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    user_id = user_data["user_id"]
    # user_id = 1
    try:
        event_type = (
            await db.execute(
                select(Event.participation_type).where(Event.id == event_id)
            )
        ).scalar_one_or_none()
        if event_type is None:
            raise HTTPException(status_code=404, detail="No event found")

        offset = (page - 1) * limit
        if event_type == ParticipationType.SINGLE:
            stmt = (
                select(
                    SingleRegistration.id.label("registration_id"),
                    SingleRegistration.status.label("registration_status"),
                    SingleRegistration.payment_status,
                    Profile.name,
                    Profile.roll_no,
                )
                .join(User, User.id == SingleRegistration.user_id)
                .outerjoin(Profile, Profile.user_id == User.id)
                .where(SingleRegistration.event_id == event_id)
                .order_by(SingleRegistration.id)
                .offset(offset)
                .limit(limit + 1)
            )
            rows = (await db.execute(stmt)).mappings().all()
            has_more = len(rows) > limit

            registrations = [
                {
                    "registration_id": row["registration_id"],
                    "registration_status": row["registration_status"].value,
                    "payment_status": row["payment_status"].value,
                    "name": row["name"],
                    "roll_number": row["roll_no"],
                }
                for row in rows[:limit]
            ]
        else:
            stmt = (
                select(
                    TeamRegistration.id.label("registration_id"),
                    TeamRegistration.team_name,
                    TeamRegistration.team_status,
                    TeamRegistration.status.label("registration_status"),
                    TeamRegistration.payment_status,
                )
                .where(TeamRegistration.event_id == event_id)
                .order_by(TeamRegistration.id)
                .offset(offset)
                .limit(limit + 1)
            )
            rows = (await db.execute(stmt)).mappings().all()
            has_more = len(rows) > limit
            page_rows = rows[:limit]
            team_ids = [row["registration_id"] for row in page_rows]
            members_by_team: dict[int, list[dict]] = {team_id: [] for team_id in team_ids}

            if team_ids:
                member_stmt = (
                    select(
                        TeamMember.team_registration_id,
                        TeamMember.role,
                        Profile.name,
                        Profile.roll_no,
                    )
                    .join(User, User.id == TeamMember.user_id)
                    .outerjoin(Profile, Profile.user_id == User.id)
                    .where(
                        TeamMember.team_registration_id.in_(team_ids),
                        TeamMember.is_removed.is_(False),
                    )
                    .order_by(TeamMember.id)
                )
                member_rows = (await db.execute(member_stmt)).mappings().all()
                for member in member_rows:
                    members_by_team[member["team_registration_id"]].append(
                        {
                            "name": member["name"],
                            "roll_number": member["roll_no"],
                            "role": member["role"].value,
                        }
                    )

            registrations = [
                {
                    "registration_id": row["registration_id"],
                    "team_name": row["team_name"],
                    "team_status": row["team_status"].value,
                    "registration_status": row["registration_status"].value,
                    "team_payment_status": row["payment_status"].value,
                    "members": members_by_team[row["registration_id"]],
                }
                for row in page_rows
            ]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event registrations retrieved successfully",
                "data": {
                    "event_id": event_id,
                    "participation_type": event_type.value,
                    "registrations": registrations,
                    "pagination": {"page": page, "limit": limit, "has_more": has_more},
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during event registration fetch by admin",
            extra={"admin_id": user_id, "event_id": event_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")
