import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header, Path
from fastapi.responses import JSONResponse

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

from db.models.auth import Profile
from db.models.team_member import TeamMember

from db.models.team_registration import(
    TeamRegistration,
    TeamRegistrationPaymentStatus,
    TeamRegistrationStatus
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
from engine.cache import get_value, set_value, delete_value



from core.config import settings


logger = logging.getLogger("user")

user_router = APIRouter()


@user_router.get("/profile")
async def get_profile_deails(
    db:AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
):
    # user_id = user_data["user_id"]
    user_id = 1
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
                    Event.event_start_time.label("event_start_data"),
                    Event.participation_type.label("event_type"),
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
                    Event.event_start_time.label("event_start_data"),
                    Event.participation_type.label("event_type"),
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
        logger.exception("exception during profile fetching", extra={"user_id": user_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal Server Error")


@user_router.get("/team-details/{team_id}")
async def team_details(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=3, refill_rate=0.2, mode="both"))
):
    # user_id = user_data["user_id"]
    user_id = 1
    try:
        team_event = (
            await db.execute(
                select(
                    Event.name,
                    TeamRegistration.team_name,
                    TeamRegistration.team_code,
                    TeamRegistration.team_status,
                    TeamRegistration.created_at,
                    TeamMember.role,
                )
                .join(
                    TeamRegistration,
                    TeamRegistration.event_id == Event.id,
                )
                .join(
                    TeamMember,
                    TeamMember.team_registration_id == TeamRegistration.id,
                )
                .where(
                    TeamRegistration.id == team_id,
                    TeamMember.user_id == user_id,
                    TeamMember.is_removed == False,
                    TeamRegistration.status == TeamRegistrationStatus.CONFIRMED,
                    TeamRegistration.payment_status.in_([
                        TeamRegistrationPaymentStatus.PAID,
                        TeamRegistrationPaymentStatus.NOT_REQUIRED,
                    ]),
                    Event.participation_type == ParticipationType.TEAM,
                    Event.status != EventStatus.DRAFT,
                )
            )
        ).first()
                
        if team_event is None:
            raise HTTPException(status_code=404, detail="Team not found or you are not an active team member",)

        event_name, team_name, team_code, team_status, team_created_at, member_role = team_event
        members = (
            await db.execute(
                select(
                    TeamMember.user_id,
                    Profile.name,
                    TeamMember.role,
                    TeamMember.created_at,
                )
                .join(Profile, Profile.user_id == TeamMember.user_id)
                .where(
                    TeamMember.team_registration_id == team_id,
                    TeamMember.is_removed.is_(False),
                )
                .order_by(TeamMember.created_at.asc(), TeamMember.user_id.asc())
            )
        ).mappings().all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Team event details retrieved successfully",
                "data": {
                    "team_id": team_id,
                    "team_name": team_name,
                    "team_code": team_code,
                    "team_role": member_role.value,
                    "team_status": team_status.value,
                    "team_joined_date": team_created_at.isoformat(),
                    "members": [
                        {
                            "user_id": member["user_id"],
                            "name": member["name"],
                            "role": member["role"].value,
                            "joined_date": member["created_at"].isoformat(),
                        }
                        for member in members
                    ],
                    "event_name": event_name,
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during team details fetching", extra={"user_id": user_id, "team_id": team_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal Server Error")


@user_router.get("/team-payment-details/{team_id}")
async def get_team_payment_details(
    team_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=3, refill_rate=0.2, mode="both")),
):
    # user_id = user_data["user_id"]
    user_id = 1
    try:
        authorized_team = (
            await db.execute(
                select(TeamRegistration.id).join(
                    TeamMember,
                    TeamMember.team_registration_id == TeamRegistration.id,
                ).where(
                    TeamRegistration.id == team_id,
                    TeamMember.user_id == user_id,
                    TeamMember.is_removed.is_(False),
                    TeamRegistration.status == TeamRegistrationStatus.CONFIRMED,
                    TeamRegistration.payment_status == TeamRegistrationPaymentStatus.PAID,
                )
            )
        ).scalar_one_or_none()

        if authorized_team is None:
            raise HTTPException(
                status_code=404,
                detail="Paid team registration not found or access denied",
            )

        payment = (
            await db.execute(
                select(Payment).where(
                    Payment.team_registration_id == team_id,
                    Payment.participation_type == PaymentParticipationType.TEAM,
                    Payment.status == PaymentStatus.SUCCESS,
                ).order_by(Payment.paid_at.desc(), Payment.id.desc())
            )
        ).scalars().first()

        if payment is None:
            raise HTTPException(status_code=404, detail="Successful team payment not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Team payment details retrieved successfully",
                "data": {
                    "team_id": team_id,
                    "payment_id": payment.id,
                    "razorpay_order_id": payment.razorpay_order_id,
                    "razorpay_payment_id": payment.razorpay_payment_id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": payment.status.value,
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during team payment details fetching",
            extra={"user_id": user_id, "team_id": team_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")
    

@user_router.get("/single-participation-details/{participation_id}")
async def get_single_participation_details(
    participation_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=3, refill_rate=0.2, mode="both")),
):
    # user_id = user_data["user_id"]
    user_id = 1

    try:
        participation = (
            await db.execute(
                select(
                    Event.name.label("event_name"),
                    SingleRegistration.created_at.label("joined_time"),
                    Profile.name.label("user_name"),
                )
                .join(Event, Event.id == SingleRegistration.event_id)
                .join(Profile, Profile.user_id == SingleRegistration.user_id)
                .where(
                    SingleRegistration.id == participation_id,
                    SingleRegistration.user_id == user_id,
                    SingleRegistration.status == SingleRegistrationStatus.CONFIRMED,
                    SingleRegistration.payment_status.in_([
                        SingleRegistrationPaymentStatus.PAID,
                        SingleRegistrationPaymentStatus.NOT_REQUIRED,
                    ]),
                    Event.status != EventStatus.DRAFT,
                )
            )
        ).mappings().one_or_none()

        if participation is None:
            raise HTTPException(
                status_code=404,
                detail="Participation not found or access denied",
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Participation details retrieved successfully",
                "data": {
                    "event_name": participation["event_name"],
                    "joined_time": participation["joined_time"].isoformat(),
                    "user_name": participation["user_name"],
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during single participation details fetching",
            extra={
                "user_id": user_id,
                "participation_id": participation_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")




@user_router.get("/single-participation-payment-details/{participation_id}")
async def get_single_participation_payment_details(
    participation_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=3, refill_rate=0.2, mode="both")),
):
    # user_id = user_data["user_id"]
    user_id = 1

    try:
        authorized_participation = (
            await db.execute(
                select(SingleRegistration.id)
                .where(
                    SingleRegistration.id == participation_id,
                    SingleRegistration.user_id == user_id,
                    SingleRegistration.status == SingleRegistrationStatus.CONFIRMED,
                    SingleRegistration.payment_status == SingleRegistrationPaymentStatus.PAID,
                )
            )
        ).scalar_one_or_none()

        if authorized_participation is None:
            raise HTTPException(status_code=404, detail="Paid participation not found or access denied")

        payment = (
            await db.execute(
                select(Payment)
                .where(
                    Payment.single_registration_id == participation_id,
                    Payment.participation_type == PaymentParticipationType.SINGLE,
                    Payment.status == PaymentStatus.SUCCESS,
                )
                .order_by(Payment.paid_at.desc(), Payment.id.desc())
            )
        ).scalars().first()

        if payment is None:
            raise HTTPException(status_code=404, detail="Successful payment not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Single participation payment details retrieved successfully",
                "data": {
                    "participation_id": participation_id,
                    "payment_id": payment.id,
                    "razorpay_order_id": payment.razorpay_order_id,
                    "razorpay_payment_id": payment.razorpay_payment_id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": payment.status.value,
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during single participation payment details fetching",extra={"user_id": user_id,"participation_id": participation_id,"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal Server Error")
