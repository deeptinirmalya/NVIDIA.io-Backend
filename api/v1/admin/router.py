from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from beanie import PydanticObjectId
from fastapi.responses import JSONResponse
from sqlalchemy import select, asc, update
from sqlalchemy.ext.asyncio import AsyncSession


from security.auth import token_required
from security.rate_limiter import rate_limiter
from db.session import get_db

from services.auditlog_service import create_audit_log

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
from db.models.auth import User, UserRole, Profile


from db.models.admin_states import AdminStats





from monitoring.logger import logging

logger = logging.getLogger("admin")

admin_router = APIRouter()


@admin_router.get("/admin-dashboard")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    user_id = user_data["user_id"]
    # user_id = 1
    try:
        stats = (
            await db.execute(
                select(
                    AdminStats.total_user,
                    AdminStats.total_events,
                    AdminStats.total_registration,
                ).where(AdminStats.id == 1)
            )
        ).mappings().one_or_none()


        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Admin dashboard retrieved successfully",
                "data": {
                    "total_user": stats["total_user"] if stats else 0,
                    "total_events": stats["total_events"] if stats else 0,
                    "total_registration": stats["total_registration"] if stats else 0
                    },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during admin_dashboard fetch by admin",
            extra={"admin_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")



@admin_router.get("/all-events")
async def get_all_events(
    search: str | None = Query(default=None, max_length=100, description="name of the event"),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(15, ge=1, le=15, description="Events per page"),
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
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
            Event.status.label("event_status"),
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
            "exception during events fetch by admin",
            extra={"admin_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.patch("/update-event-status/{event_id}/{status}")
async def update_event_status(
    event_id: int,
    status: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.5, mode="both"))
):
    user_id = user_data["user_id"]
    normalized_status = status.upper()
    valid_statuses = {EventStatus.DRAFT, EventStatus.PUBLISHED, EventStatus.CANCELLED}

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


@admin_router.get("/all-events-id")
async def get_all_events_id(
    search: str | None = Query(default=None, max_length=100, description="name of the event"),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(20, ge=1, le=20, description="Events per page"),
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
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
        ).where(
            Event.status != EventStatus.DRAFT
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



@admin_router.get("/event-registrations/{event_id}")
async def get_event_registrations(
    event_id: int,
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(15, ge=1, le=15, description="Registrations per page"),
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
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





@admin_router.get("/all-users")
async def get_students(
    roll_number: str | None = Query(None, max_length=15, description="Filter by exact roll number"),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(100, ge=1, le=100, description="Students per page"),
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    user_id = user_data["user_id"]
    try:
        stmt = (
            select(
                User.id.label("user_id"),
                Profile.name.label("name"),
                Profile.roll_no.label("roll_number"),
                Profile.contact_no.label("mobile_number"),
            )
            .join(User, User.id == Profile.user_id)
            .where(User.role == UserRole.STUDENT)
            .order_by(Profile.roll_no)
        )
        if roll_number:
            stmt = stmt.where(Profile.roll_no == roll_number.strip().upper())

        offset = (page - 1) * limit
        rows = (
            await db.execute(stmt.offset(offset).limit(limit + 1))
        ).mappings().all()
        has_more = len(rows) > limit
        students = [dict(row) for row in rows[:limit]]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Students retrieved successfully",
                "data": {
                    "students": students,
                    "pagination": {"page": page, "limit": limit, "has_more": has_more},
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during student fetch by admin",
            extra={"admin_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.get("/student-profile/{user_id}")
async def student_profile_deails(
    user_id: int,
    db:AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
):
    admin_id = user_data["user_id"]
    try:

        profile = (
            await db.execute(
                select(Profile.name, Profile.roll_no).where(Profile.user_id == user_id)
            )
        ).mappings().one_or_none()

        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")

        single_participation = (
            await db.execute(
                select(
                    SingleRegistration.id.label("participation_id"),
                    Event.name.label("event_name"),
                    Event.id.label("event_id"),
                    Event.participation_type.label("event_type"),
                    Event.event_start_time.label("event_start_data"),
                    SingleRegistration.created_at.label("joined_date")
                )
                .join(Event, Event.id == SingleRegistration.event_id)
                .where(
                    SingleRegistration.user_id == user_id,
                    SingleRegistration.status == SingleRegistrationStatus.CONFIRMED,
                    SingleRegistration.payment_status.in_([
                        SingleRegistrationPaymentStatus.PAID,
                        SingleRegistrationPaymentStatus.NOT_REQUIRED
                    ])
                    )
                .order_by(SingleRegistration.created_at.desc())
            )
        ).mappings().all()

        team_participation = (
            await db.execute(
                select(
                    TeamRegistration.id.label("participation_id"),
                    TeamRegistration.team_name,
                    Event.name.label("event_name"),
                    Event.id.label("event_id"),
                    Event.participation_type.label("event_type"),
                    Event.event_start_time.label("event_start_data"),
                    TeamMember.created_at.label("joined_date")
                )
                .join(
                    TeamRegistration,
                    TeamRegistration.id == TeamMember.team_registration_id,
                )
                .join(Event, Event.id == TeamRegistration.event_id)
                .where(
                    TeamMember.user_id == user_id,
                    TeamMember.is_removed.is_(False),
                    TeamRegistration.status == TeamRegistrationStatus.CONFIRMED,
                    TeamRegistration.payment_status.in_([
                        TeamRegistrationPaymentStatus.PAID,
                        TeamRegistrationPaymentStatus.NOT_REQUIRED
                    ])
                )
                .order_by(TeamMember.created_at.desc())
            )
        ).mappings().all()
        return JSONResponse(
            status_code=200,
            content= {
            "success": True,
            "message": "Profile and participation details retrieved successfully",
            "data": {
                "profile_details":{
                    "name": profile["name"],
                    "roll_number": profile["roll_no"]
                },
                "single_participation": [
                    {
                        **dict(participation),
                        "event_start_data": (
                            participation["event_start_data"].isoformat()
                            if participation["event_start_data"] is not None
                            else None
                        ),
                        "joined_date": participation["joined_date"].isoformat(),
                    }
                    for participation in single_participation
                ],
                "team_participation": [
                    {
                        **dict(participation),
                        "event_start_data": (
                            participation["event_start_data"].isoformat()
                            if participation["event_start_data"] is not None
                            else None
                        ),
                        "joined_date": participation["joined_date"].isoformat(),
                    }
                    for participation in team_participation
                ],
            },
            "error": None,
        }
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during profile fetching", extra={"user_id": user_id, "admin_id": admin_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal Server Error")



