import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, asc

from db.session import get_db
from security.auth import token_required
from security.rate_limiter import rate_limiter
from utils import auth_util




from db.models.event import(
    Event,
    ParticipationType
) 
from db.models.team_registration import (
    TeamRegistration,
    TeamRegistrationStatus
)

from db.models.team_member import(
    TeamMember,
    TeamMemberRole
)

from db.models.auth import (
    Profile
)

import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-TeamRedistration-Management")


superadmin_teamRegistration_management_router = APIRouter()


@superadmin_teamRegistration_management_router.patch("/cancel-team-registration/{participation_id:int}")
async def cancel_registration(
    participation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.2, mode="both"))
):
    try:
        verify_team_registration = (await db.execute(
            select(Event.id)
            .join(TeamRegistration, TeamRegistration.event_id == Event.id)
            .where(TeamRegistration.id == participation_id,
                    Event.participation_type == ParticipationType.TEAM
                    )
            )).scalar_one_or_none()
        if verify_team_registration is None:
            raise HTTPException(status_code=404, detail="invalid registration")

        res = (await db.execute(
                    update(TeamRegistration)
                    .where(TeamRegistration.id == participation_id)
                    .values(status = TeamRegistrationStatus.CANCELLED,
                            updated_at = auth_util.get_now_utc())
                ))
        if res.rowcount == 0:
            raise HTTPException(status_code=400, detail="Registration Cancel failed")

        await cServices.decrease_total_registration_count(db, 1)

        await db.commit()


        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="CANCEL_REGISTRATION",
            entity_type="TEAM_REGISTRATION",
            entity_id=participation_id,
            description="Team registration canceled by superadmin",
            metadata={"participation_id": participation_id},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Registration cancel successful",
                "data": None,
                "error": None
            }
        )
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("Exception during cancel the Team registration", extra={
            "superadmin_id": user_data["user_id"],
            "participation_id": participation_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server error")


@superadmin_teamRegistration_management_router.get("/{participation_id:int}/team-members")
async def get_team_members(
    participation_id: int,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.2, mode="both"))
):
    try:
        verify_team_registration = (await db.execute(
            select(Event.id)
            .join(TeamRegistration, TeamRegistration.event_id == Event.id)
            .where(TeamRegistration.id == participation_id,
                    Event.participation_type == ParticipationType.TEAM
                    )
            )).scalar_one_or_none()
        if verify_team_registration is None:
            raise HTTPException(status_code=404, detail="invalid registration")

        members = (await db.execute(
            select(
                    TeamMember.id.label("member_id"),
                    TeamMember.role.label("member_role"),
                    TeamMember.is_removed.label("is_removed"),
                    Profile.name.label("member_name"),
                    Profile.contact_no.label("member_contact_no"),
                    Profile.roll_no.label("member_roll_no")
            ).join(Profile, TeamMember.user_id == Profile.user_id)
            .where(TeamMember.team_registration_id == participation_id)
        )).mappings().all()

        final_result = []
        for row in members:
            row_dict = dict(row)
            if hasattr(row_dict["member_role"], "value"):
                row_dict["member_role"] = row_dict["member_role"].value
            final_result.append(row_dict)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Retrieved successfully",
                "data": final_result,
                "error": None
            }
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("Exception during fetching the Team member", extra={
            "superadmin_id": user_data["user_id"],
            "participation_id": participation_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server error")


@superadmin_teamRegistration_management_router.patch("/remove-team-member/{member_id:int}")
async def remove_team_member(
    member_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both"))
):
    try:
        res = (await db.execute(
            update(TeamMember)
            .values(
                is_removed = True,
                updated_at = auth_util.get_now_utc()
            )
            .where(TeamMember.id == member_id)
        ))

        if res.rowcount == 0:
            raise HTTPException(status_code=400, detail="Failed to remove the Team member")


        await db.commit()


        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="REMOVE_TEAM_MEMBER",
            entity_type="TEAM_REGISTRATION",
            entity_id=member_id,
            description="Team member removed by superadmin",
            metadata={"member_id": member_id},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Team member removed successfully",
                "data": None,
                "error": None
            }
        )
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("Exception during removing the Team member", extra={
            "superadmin_id": user_data["user_id"],
            "member_id": member_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server error")


@superadmin_teamRegistration_management_router.patch("/transfer-ownership/{member_id:int}")
async def transfer_ownership(
    member_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both"))
):
    try:

        new_captain = (await db.execute(
            select(TeamMember)
            .where(TeamMember.id == member_id, TeamMember.is_removed == False)
        )).scalar_one_or_none()

        if new_captain is None:
            raise HTTPException(status_code=404, detail="Team member not found")

        if new_captain.role == TeamMemberRole.CAPTAIN:
            raise HTTPException(status_code=409, detail="This member is already the captain")


        await db.execute(
            update(TeamMember)
            .where(
                TeamMember.team_registration_id == new_captain.team_registration_id,
                TeamMember.role == TeamMemberRole.CAPTAIN,
                TeamMember.is_removed == False,
            )
            .values(role=TeamMemberRole.MEMBER, updated_at=auth_util.get_now_utc())
        )


        await db.execute(
            update(TeamMember)
            .where(TeamMember.id == member_id)
            .values(role=TeamMemberRole.CAPTAIN, updated_at=auth_util.get_now_utc())
        )

        await db.commit()

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="TRANSFER_OWNERSHIP",
            entity_type="TEAM_REGISTRATION",
            entity_id=new_captain.team_registration_id,
            description="Team ownership transferred by superadmin",
            metadata={"new_captain_member_id": member_id, "team_registration_id": new_captain.team_registration_id},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Team ownership transferred successfully",
                "data": None,
                "error": None
            }
        )
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("Exception during transfer ownership", extra={
            "superadmin_id": user_data["user_id"],
            "member_id": member_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server error")