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
        
        re = await verify_superadmin_code("ADD_NEW_ADMIN", user_id, db, data.code)
        if not re["success"]:
            raise HTTPException(status_code=409, detail=re["message"])

        admin = User(
            email=data.email,
            password_hash=auth_util.hash_password(data.password),
            role=UserRole.ADMIN,
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
