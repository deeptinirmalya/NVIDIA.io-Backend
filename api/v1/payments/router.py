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

from db.models.single_registration import SingleRegistration
from db.models.team_registration import TeamRegistration, TeamRegistrationStatus, TeamRegistrationPaymentStatus


from .schemas import RazorpayPaymentVerificationRequest
from core.config import settings
from monitoring.posthog import posthog

logger = logging.getLogger("payment")

payment_router = APIRouter()




@payment_router.post("/verify-payment")
async def verify_payment_request(
    data: RazorpayPaymentVerificationRequest,
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.2, mode="both")),
):
    # user_id = user_data["user_id"]
    user_id = 1
    try:
        result = await PaymentServices.verify_payment_request_by_frontend(db, data, user_id)
        return result
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("error during verify_payment_request by frontend", extra={"data": data})
        raise HTTPException(status_code=500, detail="Internal Server Error")


@payment_router.post("/payment-status")
async def payment_status(
    code: str,
    db: AsyncSession = Depends(get_db),
    # user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.2, mode="both")),
):
    # user_id = user_data["user_id"]
    user_id = 1
    try:
        code_data = util.decode_dict(code, settings.ENCRYPTION_KEY)
        # return code_data
        if code_data.get("participation_type") == "SINGLE":
            result_of_singel_registration = (await db.execute(select(SingleRegistration).where(SingleRegistration.user_id == user_id, SingleRegistration.id == code_data.get("registration_id")))).scalar_one_or_none()
            if result_of_singel_registration is None:
                raise HTTPException(status_code=400, detail="Invalid code")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Details of this request",
                    "data": {
                        "participation_type": "SINGLE",
                        "status": result_of_singel_registration.status.value,
                        "payment_status": result_of_singel_registration.payment_status.value
                    }
                }
            )
        
        if code_data.get("participation_type") == "TEAM":
            result_of_team_registration = (await db.execute(select(TeamRegistration).where(TeamRegistration.captain_id == user_id, TeamRegistration.id == code_data.get("registration_id")))).scalar_one_or_none()
            if result_of_team_registration is None:
                raise HTTPException(status_code=400, detail="Invalid code")
            if result_of_team_registration.status == TeamRegistrationStatus.CONFIRMED and result_of_team_registration.payment_status == TeamRegistrationPaymentStatus.PAID:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Details of this request",
                        "data": {
                            "participation_type": "TEAM",
                            "status": result_of_team_registration.status.value,
                            "payment_status": result_of_team_registration.payment_status.value,
                            "team_code": result_of_team_registration.team_code
                        },
                        "error": None
                    }
                )
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Details of this request",
                    "data": {
                        "status": result_of_team_registration.status.value,
                        "payment_status": result_of_team_registration.payment_status.value,
                        "team_code": None
                    },
                    "error": None
                }
            )
        
        raise HTTPException(status_code=400, detail="Invalid code")
    except util.EncryptionError:
        logger.warning("Invalid payment status code", extra={"user_id": user_id})
        raise HTTPException(status_code=400, detail="Invalid or expired payment code")
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("error during payment_status", extra={"user_id": user_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal Server Error")