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
from engine.cache import get_value, set_value


from db.models.auth import(
    User,
    UserRole,
    UserStatus,
    Profile,
)

from db.models.auth import SuperAdminTotp
from db.models.event import Event
from db.models.single_registration import (
    SingleRegistration,
    SingleRegistrationStatus,
    SingleRegistrationPaymentStatus,
)
from db.models.team_member import TeamMember
from db.models.team_registration import (
    TeamRegistration,
    TeamRegistrationStatus,
    TeamRegistrationPaymentStatus,
)


from core.config import settings

from ..others import verify_superadmin_code
from ..schemas import NewSuperAdminRequest, AdminRegister

import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-user-Management")


superadmin_student_management_router = APIRouter()




@superadmin_student_management_router.get("/student-details")
async def get_student_participations_by_roll_number(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    roll_number: str | None = Query(default=None, description="Student roll number"),
    user_id: int | None = Query(default=None, description="Student user id"),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    try:
        if roll_number is None and user_id is None:
            raise HTTPException(status_code=400,detail="Provide either roll number or user id")

        if roll_number is not None and user_id is not None:
            raise HTTPException(status_code=400,detail="Provide either roll_number or user_id, not both")

        student_roll = None
        student_profile = None

        if roll_number is not None:
            student_roll = roll_number.strip().upper()
            student_profile = (
                await db.execute(
                    select(Profile.user_id, Profile.name, Profile.roll_no).where(
                        Profile.roll_no == student_roll
                    )
                )
            ).mappings().one_or_none()
        else:
            student_profile = (
                await db.execute(
                    select(Profile.user_id, Profile.name, Profile.roll_no).where(
                        Profile.user_id == user_id
                    )
                )
            ).mappings().one_or_none()

        if student_profile is None:
            if roll_number is not None:
                raise HTTPException(status_code=404, detail="Student not found with this roll number")
            raise HTTPException(status_code=404, detail="Student profile not found for this user id")

        student_user_id = student_profile["user_id"]
        student_roll = student_profile["roll_no"] or student_roll
        student_name = student_profile["name"]

        student_detail = (
            await db.execute(
                select(User).where(
                    User.id == student_user_id,
                    User.role == UserRole.STUDENT,
                )
            )
        ).scalar_one_or_none()
        if student_detail is None:
            raise HTTPException(status_code=404, detail="Student detail not found")

        single_rows = (
            await db.execute(
                select(
                    SingleRegistration.id.label("participation_id"),
                    Event.name.label("event_name"),
                    Event.participation_type.label("participation_type"),
                    SingleRegistration.created_at.label("joined_date"),
                    SingleRegistration.status.label("status"),
                    SingleRegistration.payment_status.label("payment_status"),
                )
                .join(Event, Event.id == SingleRegistration.event_id)
                .where(SingleRegistration.user_id == student_user_id)
                .order_by(SingleRegistration.created_at.desc())
            )
        ).mappings().all()

        team_rows = (
            await db.execute(
                select(
                    TeamRegistration.id.label("participation_id"),
                    TeamRegistration.team_name,
                    Event.name.label("event_name"),
                    Event.participation_type.label("participation_type"),
                    TeamMember.created_at.label("joined_date"),
                    TeamRegistration.status.label("status"),
                    TeamRegistration.payment_status.label("payment_status"),
                )
                .join(TeamMember, TeamMember.team_registration_id == TeamRegistration.id)
                .join(Event, Event.id == TeamRegistration.event_id)
                .where(
                    TeamMember.user_id == student_user_id,
                    TeamMember.is_removed.is_(False),
                )
                .order_by(TeamMember.created_at.desc())
            )
        ).mappings().all()

        formatted_single = [
            {
                "participation_id": row["participation_id"],
                "event_name": row["event_name"],
                "participation_type": row["participation_type"],
                "joined_date": row["joined_date"].isoformat() if row["joined_date"] else None,
                "status": row["status"].value,
                "payment_status": row["payment_status"].value,
            }
            for row in single_rows
        ]

        formatted_team = [
            {
                "participation_id": row["participation_id"],
                "team_name": row["team_name"],
                "event_name": row["event_name"],
                "participation_type": row["participation_type"],
                "joined_date": row["joined_date"].isoformat() if row["joined_date"] else None,
                "status": row["status"].value,
                "payment_status": row["payment_status"].value,
            }
            for row in team_rows
        ]

        # await create_audit_log(
        #     request=request,
        #     user_id=user_data["user_id"],
        #     action="VIEW_STUDENT_PARTICIPATIONS",
        #     entity_type="USER",
        #     entity_id=student_user_id,
        #     description="Student participation report fetched by roll number or user id",
        #     metadata={"roll_number": student_roll, "user_id": student_user_id},
        # )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Student participation details retrieved successfully",
                "data": {
                    "student_detail": {
                        "user_id": student_user_id,
                        "roll_no": student_roll,
                        "name": student_name,
                        "email": student_detail.email,
                        "status": student_detail.status,
                        "last_login": (
                            student_detail.last_login.isoformat()
                            if student_detail.last_login
                            else None
                        ),
                        "created_at": student_detail.created_at.isoformat(),
                    },
                    "single_participation": formatted_single,
                    "team_participation": formatted_team,
                },
                "error": None,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Exception during student participation fetch",
            extra={
                "roll_number": roll_number,
                "user_id": user_id,
                "admin_id": user_data["user_id"],
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@superadmin_student_management_router.patch("/block-user/{user_id}")
async def block_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both"))
):
    try:
        user = (
            await db.execute(
                select(User)
                .where(
                    User.id == user_id,
                    User.role.in_([UserRole.ADMIN, UserRole.STUDENT]),
                )
            )
        ).scalar_one_or_none()

        if user is None:
            logger.warning(
                "Invalid user id to block",extra={"user_id": user_id, "admin_id": user_data["user_id"]})
            raise HTTPException(status_code=404, detail="Invalid user id to block")

        if user.status == UserStatus.SUSPENDED:
            logger.warning("User already blocked",extra={"user_id": user_id, "admin_id": user_data["user_id"]})
            raise HTTPException(status_code=409, detail="User already blocked")

        user.status = UserStatus.SUSPENDED
        user.token_version = (user.token_version or 0) + 1
        await db.commit()

        await cServices.increase_decrease_blocked_count(db, is_block=True)

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="BLOCK_USER",
            entity_type="USER",
            entity_id=user_id,
            description="User blocked by superadmin",
            metadata={"user_id": user_id},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User blocked",
                "data": None,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("Exception during user blocking",extra={"superadmin_id": user_data["user_id"], "user_id": user_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")

    
@superadmin_student_management_router.patch("/unblock-user/{user_id}")
async def unblock_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both"))
):
    try:
        user = (
            await db.execute(
                select(User)
                .where(
                    User.id == user_id,
                    User.role.in_([UserRole.ADMIN, UserRole.STUDENT]),
                )
            )
        ).scalar_one_or_none()

        if user is None:
            logger.warning("Invalid user id to unblock",extra={"user_id": user_id, "admin_id": user_data["user_id"]})
            raise HTTPException(status_code=404, detail="Invalid user id to unblock")

        if user.status != UserStatus.SUSPENDED:
            logger.warning("User is not suspended",extra={"user_id": user_id, "admin_id": user_data["user_id"]})
            raise HTTPException(status_code=409, detail="User is not suspended")

        user.status = UserStatus.ACTIVE
        user.token_version = (user.token_version or 0) + 1
        await db.commit()

        await cServices.increase_decrease_blocked_count(db, is_block=False)

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="UNBLOCK_USER",
            entity_type="USER",
            entity_id=user_id,
            description="User unblocked by superadmin",
            metadata={"user_id": user_id},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User unblocked",
                "data": None,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("Exception during user unblocking",extra={"superadmin_id": user_data["user_id"], "user_id": user_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")


@superadmin_student_management_router.patch("/logout-user/{user_id}")
async def logout_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both"))
):
    try:
        user = (
            await db.execute(
                select(User)
                .where(
                    User.id == user_id,
                    User.role.in_([UserRole.ADMIN, UserRole.STUDENT]),
                )
            )
        ).scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=404, detail="Invalid user id to logout")

        user.token_version = (user.token_version or 0) + 1
        await db.commit()

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="LOGOUT_USER",
            entity_type="USER",
            entity_id=user_id,
            description="User logged out by superadmin",
            metadata={"user_id": user_id},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User logged out",
                "data": None,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "Exception during user logout",extra={"superadmin_id": user_data["user_id"], "user_id": user_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")

