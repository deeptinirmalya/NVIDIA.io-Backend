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
from db.models.event import(
    Event,
    ParticipationType
) 
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

from db.models.payment import(
    Payment,
    PaymentParticipationType,
    PaymentStatus
)


from core.config import settings

from ..others import verify_superadmin_code

import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-payment-Management")


superadmin_payment_management_router = APIRouter()

@superadmin_payment_management_router.get("/single-registration/{particpatin_id}/payment-details")
async def single_registration_payment_details(
    participation_id: int,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.2, mode="both"))
):
    try:
        event_details = (await db.execute(
            select(
                SingleRegistration.user_id.label("participate_user_id"),
                Event.name.label("event_name"),
                Event.is_paid.label("paid_event")
            )
            .join(Event, Event.id == SingleRegistration.event_id)
            .where(
                SingleRegistration.id == participation_id,
                Event.participation_type == ParticipationType.SINGLE,
            )
        )).mappings().one_or_none()
        if event_details is None:
            raise HTTPException(status_code=404, detail="invalid participation Id")

        if not event_details["paid_event"]:
            raise HTTPException(status_code=409, detail="Event is not a paid event")

        
        payment_details = (await db.execute(
            select(Payment).where(
                Payment.participation_type == PaymentParticipationType.SINGLE,
                Payment.single_registration_id == participation_id,
            )
        )).scalar_one_or_none()
        if payment_details is None:
            raise HTTPException(status_code=404, detail="No payment details found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "fatched Payment detais",
                "data": {
                    "id": payment_details.id,
                    "amount": payment_details.amount,
                    "currency": payment_details.currency,
                    "status": payment_details.status.value if payment_details.status else None,
                    "razorpay_order_id": payment_details.razorpay_order_id,
                    "razorpay_payment_id": payment_details.razorpay_payment_id,
                    "razorpay_signature": payment_details.razorpay_signature,
                    "created_at": payment_details.created_at.isoformat() if payment_details.created_at else None,
                    "paid_at": payment_details.paid_at.isoformat() if payment_details.paid_at else None,
                },
                "error": None,
            },
        )
        
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during payment details view", extra={
            "superadin_id": user_data["user_id"],
            "particicpation_id": participation_id,
            "participatio_type": "SINGLE",
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    
@superadmin_payment_management_router.get("/team-registration/{particpatin_id}/payment-details")
async def team_registration_payment_details(
    participation_id: int,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.2, mode="both"))
):
    try:
        pass
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during payment details view", extra={
            "superadin_id": user_data["user_id"],
            "particicpation_id": participation_id,
            "participatio_type": "TEAM",
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server Error")
