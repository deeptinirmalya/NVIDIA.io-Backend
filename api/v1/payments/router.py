import base64
import uuid
import httpx
import logging
import binascii
import secrets
import json
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
import datetime
from typing import Optional
from razorpay.errors import SignatureVerificationError

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select, cast, String

from db.models.event import (
    Event,
    EventCategory,
    EventStatus,
    GenderType,
    ParticipationType
)

from db.models.single_registration import(
    SingleRegistrationStatus,
    SingleRegistrationPaymentStatus,
    SingleRegistration
)

from db.models.payment import(
    Payment,
    PaymentParticipationType,
    PaymentStatus
)

from db.session import get_db
# from security import auth as security
from engine.cache import redis_client
from security.rate_limiter import rate_limiter
from security.auth import get_client_info, token_required
from utils import auth_util, util
from templates import email_templates 
from engine.cache import get_value, set_value, delete_value


from services.payment_service import PaymentServices



from .schemas import RazorpayPaymentVerificationRequest
from core.config import settings
from monitoring.posthog import posthog

logger = logging.getLogger("payment")

payment_router = APIRouter()




@payment_router.post("/verify-payment")
async def verify_payment_request(
    data: RazorpayPaymentVerificationRequest,
    db: AsyncSession = Depends(get_db),
    # user_id: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.2, mode="both")),
):
    user_id = 1 # leter i will cheche ti the actual jwt user id
    try:
        result = await PaymentServices.verify_payment_request_by_frontend(db, data, user_id)
        return result
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("error during verify_payment_request by frontend", extra={"data": data})
        raise HTTPException(status_code=500, detail="Internal Server Error")