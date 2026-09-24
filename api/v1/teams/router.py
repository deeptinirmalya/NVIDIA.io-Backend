import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
import datetime
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from db.session import get_db
# from security import auth as security
from security.rate_limiter import rate_limiter
from security.auth import token_required
from utils import auth_util

from services.registration_service import RegistrationService

from db.models.team_registration import(
    TeamRegistration,
    TeamRegistrationStatus,
    TeamStatus
)

from db.models.event import (
    Event,
    EventStatus,
    ParticipationType
)

from db.models.team_member import TeamMember, TeamMemberRole


logger = logging.getLogger("teams")

teams_router = APIRouter()


def is_valid_team_name(value):
    if len(value) > 20:
        return False
    return bool(re.fullmatch(r'[A-Za-z0-9_]+', value))

@teams_router.post("/create/team/{event_id}/{team_name}")
async def participate_on_team_event(
    event_id: int,
    team_name: str,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.2, mode="user")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    user_id = user_data["user_id"]
    if not is_valid_team_name(team_name):
        logger.warning("invalid team name", extra={"user_id": user_id, "team_name": team_name})
        raise HTTPException(status_code=422, detail="Invalid team name")
    try:
        event_details = await RegistrationService.check_team_event_availability_for_participation(db, event_id, user_id)
        if not event_details["data"].get("is_paid"):  # free event
            return await RegistrationService.check_or_create_team_free_registration(db, event_id, user_id, team_name)
            # check or create registration and return its response
        else:
            if not idempotency_key:
                raise HTTPException(status_code=400, detail="Idempotency Key  is required for events")

            entry_result = await RegistrationService.check_or_create_team_paid_registration(db, event_id, user_id, idempotency_key, team_name)

            if isinstance(entry_result, JSONResponse):
                return entry_result
            
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(f"exception during team reistration {event_id}", extra={"user_id": user_id, "event_id": event_id})
        raise HTTPException(status_code=500, detail="Internal server error")



@teams_router.post("/join-team/{team_code}/{event_id}")
async def join_team(
    team_code: str,
    event_id: int,
    db: AsyncSession= Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.5, mode="user"))

):
    # user_id = 1 
    user_id = user_data["user_id"]
    try:
        event_details = (
            await db.execute(
                select(Event).where(
                    Event.id == event_id,
                    Event.participation_type == ParticipationType.TEAM,
                    Event.status == EventStatus.PUBLISHED,
                )
            )
        ).scalar_one_or_none()
        
        if event_details is None:
            logger.warning(f"event not found  {event_id}")
            raise HTTPException(status_code=404, detail="Invalid Event")
        
        team_code_details = (
            await db.execute(
                select(TeamRegistration).where(
                    TeamRegistration.team_code == team_code, 
                    TeamRegistration.event_id == event_id
                    ).with_for_update()
                )
            ).scalar_one_or_none()
        if team_code_details is None:
            logger.warning(f"event not found with event code {team_code}")
            raise HTTPException(status_code=404, detail="Invalid Team code")

        active_member = (
            await db.execute(
                select(func.count(TeamMember.id)).where(
                    TeamMember.team_registration_id == team_code_details.id, 
                    TeamMember.is_removed == False)
                    )
                ).scalar()
        
        if active_member > event_details.max_team_size:
            logger.warning(f"Strict action needed by admin Team over loaded or reached max size team code:- {team_code}")
            raise HTTPException(status_code=409, detail="Team is full")
        
        if active_member == event_details.max_team_size:
            logger.warning(f"Team over loaded or reached max size team code:- {team_code}")
            raise HTTPException(status_code=409, detail="Team is full")
        
        
        is_already_in_the_event = (
            await db.execute(
                select(TeamMember).where(
                    TeamMember.user_id == user_id, 
                    TeamMember.event_id == event_id, 
                    TeamMember.is_removed == False
                    )
                )
            ).scalar_one_or_none()
        if is_already_in_the_event is not None:
            raise HTTPException(status_code=409, detail="Already in this event")

        if team_code_details.status != TeamRegistrationStatus.CONFIRMED:
            raise HTTPException(status_code=409, detail="Evenet may not confirmed")
        
        if team_code_details.payment_status.value not in ["PAID", "NOT_REQUIRED"]:
            raise HTTPException(status_code=409, detail="Event may not paid yet")

        # insert 
        new_team_member = TeamMember(
            team_registration_id = team_code_details.id,
            user_id = user_id,
            event_id = event_id,
            role = TeamMemberRole.MEMBER,
            created_at = auth_util.get_now_utc()
        )

        db.add(new_team_member)
        logger.info("New member added", extra={"event_id": event_id, "team_code": team_code, "user_id": user_id})

        new_team_size = active_member + 1 
        # Update team status 
        if new_team_size >= event_details.max_team_size:
            team_code_details.status = TeamStatus.FULL

        if new_team_size >= event_details.min_team_size:
            team_code_details.status = TeamStatus.ELIGIBLE


        await db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Team join successfully",
                "data": None,
                "error": None
            }
        )

    except HTTPException as httpe:
        raise httpe
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="User is already in this team")
    except Exception as e:
        await db.rollback()
        logger.exception("exception during team joining", extra={"team_code": team_code, "user_id": user_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal Server error")
