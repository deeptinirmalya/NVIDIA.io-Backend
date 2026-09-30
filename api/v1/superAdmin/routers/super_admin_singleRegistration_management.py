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




import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-SingleRedistration-Management")


superadmin_singleRegistration_management_router = APIRouter()

@superadmin_singleRegistration_management_router.patch("/cancel-single-registration/{participation_id:int}")
async def cancle_registartion(
    participation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.2, mode="both"))
):
    try:
        verify_single_registration = (await db.execute(
            select(Event.id)
            .join(SingleRegistration, SingleRegistration.event_id == Event.id)
            .where(SingleRegistration.id == participation_id,
                    Event.participation_type == ParticipationType.SINGLE
                    )
            )).scalar_one_or_none()
        if verify_single_registration is None:
            raise HTTPException(status_code=404, detail="invalid registration")

        res = (await db.execute(
            update(SingleRegistration)
            .where(SingleRegistration.id == participation_id)
            .values(status = SingleRegistrationStatus.CANCELLED,
                    updated_at = auth_util.get_now_utc())
        ))
        if res.rowcount == 0:
            raise HTTPException(status_code=400, detail="Registration Cancel failed")

        await cServices.decrease_total_registration_count(db, 1)

        await db.commit()


        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="CANCEL_REGISTRATION",
            entity_type="SINGLE_REGISTRATION",
            entity_id=participation_id,
            description="Single registration canceled by superadmin",
            metadata={"participation_id": participation_id},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Registration cancel successful",
                "data": None,
                "error": None
            }
        )
        
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("Exception during cancel a single registration", extra={"participation_id": participation_id, "super_admin_id": user_data["user_id"], "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal Server Error")