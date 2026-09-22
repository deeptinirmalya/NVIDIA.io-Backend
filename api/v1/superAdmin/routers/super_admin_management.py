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


from core.config import settings
from monitoring.posthog import posthog

from ..others import request_code_to_superadmin

logger = logging.getLogger("Super-admin-Management")


superadmin_management_router = APIRouter()

@superadmin_management_router.post("/add-super-admin")
async def add_super_admin(
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=3, refill_rate=0.1, mode="both"))
):
    await request_code_to_superadmin("for new admin", 1, db)

    return "success"