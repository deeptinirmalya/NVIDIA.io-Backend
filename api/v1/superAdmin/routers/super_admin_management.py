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
    UserStatus
)

from db.models.auth import SuperAdminTotp


from core.config import settings

from ..others import request_code_to_superadmin, verify_superadmin_code
from ..schemas import NewSuperAdminRequest

logger = logging.getLogger("Super-admin-Management")


superadmin_management_router = APIRouter()

# REASON_TO_REQUEST_CODE = 

# re = await request_code_to_superadmin("NEW_SUPER_ADMIN_ADD", user_id, db)
# if not re["success"]:
#     raise HTTPException(status_code=409, detail=re["message"])

@superadmin_management_router.post("/add-super-admin")
async def add_super_admin(
    data: NewSuperAdminRequest,
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=3, refill_rate=0.1, mode="both"))
):
    # user_id = user_data["user_id"]
    user_id = 1

    now = auth_util.get_now_utc()

    try:
        s, m = auth_util.validate_password(data.password)
        if not s:
            raise HTTPException(status_code=422, detail=m)

        existing_email = (await db.execute(select(User.id).where(User.email == data.email.lower()))).scalar_one_or_none()
        if existing_email is not None:
            raise HTTPException(status_code=422, detail="Email already exist")

        re = await verify_superadmin_code("NEW_SUPER_ADMIN_ADD", user_id, db, data.code)
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
        raise httpe
    except Exception as e:
        logger.exception("Exception during new super admin add", extra={
            "user_id": user_id,
            "email": str(data.email)
        })
        raise HTTPException(status_code=500, detail="Internal server error")

