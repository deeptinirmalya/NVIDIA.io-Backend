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


from ..schemas import NewSuperAdminRequest
from ..others import verify_superadmin_code

import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-superadmin-Management")


superadmin_superadmin_management_router = APIRouter()


@superadmin_superadmin_management_router.post("/add-super-admin")
async def add_super_admin(
    data: NewSuperAdminRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=1, refill_rate=0.01, mode="both"))
):
    user_id = user_data["user_id"]
    # user_id = 1

    now = auth_util.get_now_utc()

    try:
        s, m = auth_util.validate_password(data.password)
        if not s:
            raise HTTPException(status_code=422, detail=m)

        existing_email = (await db.execute(select(User.id).where(User.email == data.email.lower()))).scalar_one_or_none()
        if existing_email is not None:
            raise HTTPException(status_code=422, detail="Email already exist")

        re = await verify_superadmin_code("ADD_NEW_SUPER_ADMIN", user_id, db, data.code)
        if not re["success"]:
            raise HTTPException(status_code=409, detail=re["message"])

        _, enc_secret, qr_base64 = await auth_util.generate_totp_qr(str(data.email))

        new_superadmin = User(
            email = data.email,
            password_hash = auth_util.hash_password(data.password),
            role = UserRole.SUPERADMIN,
            is_verified = True,
            status = UserStatus.ACTIVE,
            created_at = now
        )
        db.add(new_superadmin)
        await db.flush()
        await db.refresh(new_superadmin)

        new_totp = SuperAdminTotp(
            user_id = new_superadmin.id,
            secret_key = enc_secret,
            created_at = now
        )
        db.add(new_totp)

        await db.commit()

        #call the count service
        await cServices.increase_superadmin_count(db)

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="NEW_SUPERADMIN",
            entity_type="SUPERADMIN",
            entity_id=new_superadmin.id,
            description="New superadmin added by super adminadmin",
            metadata={
                "new_superadmin_data": data,
            },
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "New super admin added scan the Qr code with google authontication app",
                "data": {
                    "base64": qr_base64
                },
                "error": None
            }
        )
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("Exception during new super admin add", extra={
            "user_id": user_id,
            "email": str(data.email),
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal server error")
