import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, asc

from db.session import get_db
from security.auth import token_required
from security.rate_limiter import rate_limiter
from utils import auth_util





from ..schemas import EmailSentRequest
from ..others import verify_superadmin_code

import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-notification-Management")


superadmin_notification_management_router = APIRouter()
