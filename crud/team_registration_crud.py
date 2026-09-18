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


from db.models.team_registration import(
    TeamRegistration,
    TeamRegistrationPaymentStatus,
    TeamRegistrationStatus
)

from db.models.team_member import(
    TeamMember,
    TeamMemberRole
)

from utils import util, auth_util
from engine.cache import get_value


logger = logging.getLogger("Single_registration_crud")

class TeamregistrationCrudService:

    # ======================== FOR  FREE EVENTS ===========================

    @staticmethod
    async def create_free_team_participation(
        db: AsyncSession,
        event_id: int,
        user_id: int,
        team_name: str
    ):
        try:
            team_name = team_name.upper()
            
            team_name_stmt = select(TeamRegistration.id).where(TeamRegistration.team_name == team_name, TeamRegistration.event_id == event_id)
            existing_team_name = (await db.execute(team_name_stmt)).scalar_one_or_none()
            if existing_team_name is not None:
                logger.warning(f"team name alreday exist  {event_id}", extra={"event_id": event_id, "user_id": user_id})
                raise HTTPException(status_code=409, detail="Team name alreday existd")
            
            team_code = util.generate_random_event_code(6)
            new_free_team_registration = TeamRegistration(
                captain_id = user_id,
                team_code = team_code,
                team_name = team_name,
                event_id = event_id,
                status = TeamRegistrationStatus.CONFIRMED,
                payment_status = TeamRegistrationPaymentStatus.NOT_REQUIRED,
                created_at = auth_util.get_now_utc()
            )
            db.add(new_free_team_registration)
            await db.flush()
            await db.refresh(new_free_team_registration)

            new_tem_member_entry = TeamMember(
                team_registration_id = new_free_team_registration.id,
                user_id = user_id,
                event_id = event_id,
                role = TeamMemberRole.CAPTAIN,
                created_at = auth_util.get_now_utc()
            )
            db.add(new_tem_member_entry)

            await db.commit()

            logger.info(f"User create team  on {event_id} single", extra={"event_id": event_id, "user_id": user_id})

            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": f"Team create  success full team code : {team_code} share only with you team member",
                    "data": {
                        "team_code": team_code
                    },
                    "error": None
                }
            )
        except HTTPException as httpe:
            await db.rollback()
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
        user_id: int,
        team_name: str
    ):
        try:
            team_code = util.generate_random_event_code(6)
            
            team_name = team_name.upper()
            existing_team_name_check = (await db.execute(select(TeamRegistration.id).where(TeamRegistration.team_name == team_name, TeamRegistration.event_id == event_id))).scalar_one_or_none()
            if existing_team_name_check is not None:
                raise HTTPException(status_code=409, detail="Team name already exist")
            
            new_paid_team_registration = TeamRegistration(
                captain_id = user_id,
                team_code = team_code,
                team_name = team_name,
                event_id = event_id,
                status = SingleRegistrationStatus.PENDING,
                payment_status = SingleRegistrationPaymentStatus.PENDING,
                created_at = auth_util.get_now_utc()
            )
            db.add(new_paid_team_registration)
            await db.flush()
            await db.refresh(new_paid_team_registration)

            new_tem_member_entry = TeamMember(
                team_registration_id = new_paid_team_registration.id,
                user_id = user_id,
                event_id = event_id,
                role = TeamMemberRole.CAPTAIN,
                created_at = auth_util.get_now_utc()
            )
            db.add(new_tem_member_entry)

            return new_paid_team_registration
        except HTTPException as httpe:
            raise httpe
        except Exception as e:
            await db.rollback()
            logger.exception("Exception in SingleregistrationService – intialize_starter_paid_registration", extra={"event_id": event_id, "user_id": user_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="Server busy")