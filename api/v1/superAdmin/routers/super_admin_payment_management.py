import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, asc

from db.session import get_db
from security.auth import token_required
from security.rate_limiter import rate_limiter
from utils import auth_util




from db.models.event import(
    Event,
    ParticipationType
) 
from db.models.single_registration import (
    SingleRegistration,
    SingleRegistrationStatus,
    SingleRegistrationPaymentStatus,
)


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



import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-payment-Management")


superadmin_payment_management_router = APIRouter()

@superadmin_payment_management_router.get("/single-registration/{particpation_id}/payment-details")
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
                    "failure_reason": payment_details.failure_reason,
                    "gateway_error_code": payment_details.gateway_error_code,
                    "created_at": payment_details.created_at.isoformat() if payment_details.created_at else None,
                    "paid_at": payment_details.paid_at.isoformat() if payment_details.paid_at else None,
                    "process_at": payment_details.process_at.isoformat() if payment_details.process_at else None,
                    "failed_at": payment_details.failed_at.isoformat() if payment_details.failed_at else None,
                    "refund_at": payment_details.refund_at.isoformat() if payment_details.refund_at else None,

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
        event_details = (await db.execute(
            select(
                TeamRegistration.captain_id.label("participate_captain_id"),
                Event.name.label("event_name"),
                Event.is_paid.label("paid_event")
            )
            .join(Event, Event.id == TeamRegistration.event_id)
            .where(
                TeamRegistration.id == participation_id,
                Event.participation_type == ParticipationType.TEAM,
            )
        )).mappings().one_or_none()
        if event_details is None:
            raise HTTPException(status_code=404, detail="invalid participation Id")

        if not event_details["paid_event"]:
            raise HTTPException(status_code=409, detail="Event is not a paid event")

        
        payment_details = (await db.execute(
            select(Payment).where(
                Payment.participation_type == PaymentParticipationType.TEAM,
                Payment.team_registration_id == participation_id,
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
                    "failure_reason": payment_details.failure_reason,
                    "gateway_error_code": payment_details.gateway_error_code,
                    "created_at": payment_details.created_at.isoformat() if payment_details.created_at else None,
                    "paid_at": payment_details.paid_at.isoformat() if payment_details.paid_at else None,
                    "process_at": payment_details.process_at.isoformat() if payment_details.process_at else None,
                    "failed_at": payment_details.failed_at.isoformat() if payment_details.failed_at else None,
                    "refund_at": payment_details.refund_at.isoformat() if payment_details.refund_at else None,

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
            "participatio_type": "TEAM",
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server Error")


@superadmin_payment_management_router.patch("/update/{paynment_id}/status/{status_type}")
async def update_payment_status(
    payment_id: int,
    status_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both"))
):
    try:
        normalized_status = status_type.upper()
        now = auth_util.get_now_utc()
        if normalized_status not in ["SUCCESS", "REFUND"]:
            raise HTTPException(status_code=400, detail="Invalid Status Type")

        payment_details = (await db.execute(
            select(Payment)
            .where(
                Payment.id == payment_id
            )
        )).scalar_one_or_none()

        if payment_details is None:
            raise HTTPException(status_code=404, detail="Payment details not found")

        if payment_details.participation_type == PaymentParticipationType.SINGLE:
            if normalized_status == "SUCCESS":

                if payment_details.status == PaymentStatus.SUCCESS:
                    raise HTTPException(status_code=409, detail="alreday in success stage")
                
                res = (await db.execute(
                    update(SingleRegistration)
                    .values(
                        payment_status=SingleRegistrationPaymentStatus.PAID,
                        status=SingleRegistrationStatus.CONFIRMED,
                        updated_at=now,
                    )
                    .where(SingleRegistration.id == payment_details.single_registration_id)
                ))
                if res.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Registration not found may deleted")

                payment_details.status = PaymentStatus.SUCCESS
                payment_details.updated_at = now
                payment_details.paid_at = now

                await cServices.increase_total_success_payment_count(db, int(payment_details.amount))

            if normalized_status == "REFUND":
                res = (await db.execute(
                    update(SingleRegistration)
                    .values(
                        payment_status=SingleRegistrationPaymentStatus.REFUNDED,
                        status=SingleRegistrationStatus.CANCELLED,
                        updated_at=now,
                    )
                    .where(SingleRegistration.id == payment_details.single_registration_id)
                ))
                if res.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Registration not found may deleted")

                payment_details.status = PaymentStatus.REFUNDED
                payment_details.updated_at = now
                payment_details.refund_at = now

        if payment_details.participation_type == PaymentParticipationType.TEAM:
            if normalized_status == "SUCCESS":
                if payment_details.status == PaymentStatus.SUCCESS:
                    raise HTTPException(status_code=409, detail="alreday in success stage")
                res = (await db.execute(
                    update(TeamRegistration)
                    .values(
                        payment_status=TeamRegistrationPaymentStatus.PAID,
                        status=TeamRegistrationStatus.CONFIRMED,
                        updated_at=now,
                    )
                    .where(TeamRegistration.id == payment_details.team_registration_id)
                ))
                if res.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Registration not found may deleted")

                payment_details.status = PaymentStatus.SUCCESS
                payment_details.updated_at = now
                payment_details.paid_at = now
                await cServices.increase_total_success_payment_count(db, int(payment_details.amount))

            if normalized_status == "REFUND":
                res = (await db.execute(
                    update(TeamRegistration)
                    .values(
                        payment_status=TeamRegistrationPaymentStatus.REFUNDED,
                        status=TeamRegistrationStatus.CANCELLED,
                        updated_at=now,
                    )
                    .where(TeamRegistration.id == payment_details.team_registration_id)
                ))
                if res.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Registration not found may deleted")

                payment_details.status = PaymentStatus.REFUNDED
                payment_details.updated_at = now
                payment_details.refund_at = now

        await db.commit()

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="MODIFY_PAYMENT_STATUS",
            entity_type="PAYMENT",
            entity_id=payment_id,
            description="Payment Status updated by superadmin",
            metadata={"payment_id": payment_id, "status_type": normalized_status},
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Status update to {normalized_status}",
                "data": None,
                "error": None
            }
        )

        
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("exception during update_payment_status", extra={
            "superadmin_id": user_data["user_id"],
            "payment_id": payment_id,
            "Error": str(e)
        })
        raise HTTPException(status_code=500, detail="Internal Server error")