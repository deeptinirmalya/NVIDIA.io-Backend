import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, asc

from db.session import get_db
from security.auth import token_required
from security.rate_limiter import rate_limiter
from utils import auth_util



from db.models.auth import(
    User,
    UserRole,
    UserStatus,
    SuperAdminTotp
) 


from ..schemas import AdminRegister
from ..others import verify_superadmin_code

import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-admin-Management")


superadmin_admin_management_router = APIRouter()



@superadmin_admin_management_router.post("/add-admin")
async def register_admin(
    data: AdminRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=2, refill_rate=0.1, mode="both"))
):
    try:
        user_id = user_data["user_id"]

        stmt = select(User).where(User.email == data.email)
        existing_user = (await db.execute(stmt)).scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")

        is_valid, message = auth_util.validate_password(data.password)
        if not is_valid:
            raise HTTPException(status_code=422, detail=message)
        
        # re = await verify_superadmin_code("ADD_NEW_ADMIN", user_id, db, data.code)
        # if not re["success"]:
        #     raise HTTPException(status_code=409, detail=re["message"])

        admin = User(
            email=data.email,
            password_hash=auth_util.hash_password(data.password),
            role=UserRole.ADMIN,
            is_verified = True,
            status = UserStatus.ACTIVE,
            created_at=auth_util.get_now_utc(),
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        await cServices.increase_admin_count(db)

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="NEW_ADMIN",
            entity_type="ADMIN",
            entity_id=admin.id,
            description="New admin added by admin",
            metadata={
                "new_admin_data": data.email,
            },
        )
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Register success full",
                "data": None,
                "error": None
            }
        )

    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("Exception during admin register", extra={"email": data.email})
        raise HTTPException(status_code=500, detail="Internal Serevr error")

@superadmin_admin_management_router.get("/all-admins")
async def all_admins(
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both"))
):
    try:
        admins = (await db.execute(
            select(User.id, User.email, User.created_at, User.status, User.last_login)
            .where(User.role == UserRole.ADMIN)
        )).mappings().all()

        admin_data = [
            {
                "id": admin["id"],
                "email": admin["email"],
                "created_at": admin["created_at"].isoformat() if admin["created_at"] else None,
                "status": admin["status"].value if admin["status"] else None,
                "last_login": admin["last_login"].isoformat() if admin["last_login"] else None,
            }
            for admin in admins
        ]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Admins retrieved successfully",
                "data": admin_data,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during fetching all admins", extra={
            "superadmin_id": user_data["user_id"],
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server error")





@superadmin_admin_management_router.patch("/block-admin/{user_id}")
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
                    User.role == UserRole.ADMIN,
                )
            )
        ).scalar_one_or_none()

        if user is None:
            logger.warning(
                "Invalid admin id to block",extra={"user_id": user_id, "admin_id": user_data["user_id"]})
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
            action="BLOCK_ADMIN",
            entity_type="ADMIN",
            entity_id=user_id,
            description="ADMIN blocked by superadmin",
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


@superadmin_admin_management_router.patch("/unblock-admin/{user_id}")
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
                    User.role == UserRole.ADMIN,
                )
            )
        ).scalar_one_or_none()

        if user is None:
            logger.warning("Invalid admin id to unblock",extra={"user_id": user_id, "admin_id": user_data["user_id"]})
            raise HTTPException(status_code=404, detail="Invalid user id to unblock")

        if user.status != UserStatus.SUSPENDED:
            logger.warning("admin is not suspended",extra={"user_id": user_id, "admin_id": user_data["user_id"]})
            raise HTTPException(status_code=409, detail="User is not Blocked")

        user.status = UserStatus.ACTIVE
        user.token_version = (user.token_version or 0) + 1
        await db.commit()

        await cServices.increase_decrease_blocked_count(db, is_block=False)

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="UNBLOCK_ADMIN",
            entity_type="ADMIN",
            entity_id=user_id,
            description="admin unblocked by superadmin",
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
