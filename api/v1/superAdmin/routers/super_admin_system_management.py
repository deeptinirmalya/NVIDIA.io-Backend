import logging
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import JSONResponse


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from db.session import get_db
from security.auth import token_required
from security.rate_limiter import rate_limiter
from engine.cache import delete_values, set_value


from db.models.admin_states import AdminStats
from db.models.audit_log import AuditLog
from db.models.auth import User
from db.models.event import Event
from db.models.system_setting import SystemSetting


from ..others import request_code_to_superadmin
from ..schemas import SystemSettingToggleRequest

from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-system-Management")


superadmin_system_management_router = APIRouter()

REASON_TO_REQUEST_CODE = ["ADD_NEW_SUPER_ADMIN", "ADD_NEW_ADMIN"]



@superadmin_system_management_router.get("/settings")
async def list_system_settings(
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    user_id = user_data["user_id"]
    try:
        result = await db.execute(
            select(
                SystemSetting.id,
                SystemSetting.setting_key,
                SystemSetting.toggle_on,
                SystemSetting.last_used_at,
            ).order_by(SystemSetting.setting_key)
        )
        settings_list = [
            {
                "setting_id": row.id,
                "setting_key": row.setting_key,
                "toggle_on": row.toggle_on,
                "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            }
            for row in result.all()
        ]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "System settings retrieved successfully",
                "data": settings_list,
                "error": None,
            },
        )
    except Exception as e:
        logger.exception(
            "exception during system settings retrieval",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@superadmin_system_management_router.delete("/clear-cache")
async def clear_event_and_setting_cache(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=2, refill_rate=0.1, mode="both")),
):
    user_id = user_data["user_id"]
    try:
        setting_keys = (await db.scalars(select(SystemSetting.setting_key))).all()
        cache_keys = {
            "all_events:summary",
            *setting_keys,
        }
        deleted_key_count = await delete_values(sorted(cache_keys))

        await create_audit_log(
            request=request,
            user_id=user_id,
            action="APPLICATION_CACHE_CLEARED",
            entity_type="CACHE",
            description="Event and system-setting caches cleared by superadmin",
            metadata={"deleted_key_count": deleted_key_count},
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event and system-setting caches cleared successfully",
                "data": {"deleted_key_count": deleted_key_count},
                "error": None,
            },
        )
    except Exception as e:
        logger.exception(
            "exception during event and system-setting cache clearing",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@superadmin_system_management_router.patch("/change-settings")
async def toggle_system_setting(
    setting_data: SystemSettingToggleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=5, refill_rate=0.2, mode="both")),
):
    user_id = user_data["user_id"]
    try:
        setting = await db.scalar(
            select(SystemSetting)
            .where(
                SystemSetting.id == setting_data.id,
                SystemSetting.setting_key == setting_data.setting_key,
            )
            .with_for_update()
        )
        if setting is None:
            raise HTTPException(status_code=404, detail="System setting not found")
        if setting.toggle_on is None:
            raise HTTPException(
                status_code=409,
                detail="System setting toggle value must be true or false",
            )

        previous_value = setting.toggle_on
        setting.toggle_on = not previous_value
        await db.commit()


        await set_value(setting.setting_key, setting.toggle_on, None)

        await create_audit_log(
            request=request,
            user_id=user_id,
            action="SYSTEM_SETTING_TOGGLED",
            entity_type="SYSTEM_SETTING",
            entity_id=setting.id,
            description="System setting toggled by superadmin",
            metadata={
                "setting_key": setting.setting_key,
                "previous_value": previous_value,
                "updated_value": setting.toggle_on,
            },
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "System setting updated successfully",
                "data": None,
                "error": None,
            },
        )
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception(
            "exception during system setting toggle",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@superadmin_system_management_router.post("/request-for-code")
async def request_code_to_moderator(
    reason: str,
    db : AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=2, refill_rate=0.1, mode="both"))
):
    # user_id = 1
    user_id = user_data["user_id"]
    try:
        if reason.upper() not in REASON_TO_REQUEST_CODE:
            raise HTTPException(status_code=404, detail="Invalid reason to request code")

        re = await request_code_to_superadmin(reason, user_id, db)
        if not re["success"]:
            logger.warning("error during requesting a code in fun request_code_to_superadmin", extra={
                "user_id": user_id,
                "reason": reason
            })
            raise HTTPException(status_code=409, detail=re["message"])

        logger.info("code request to moderate", extra={
            "user_i": user_id,
            "reason": reason
        })
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "code send success fully",
                "data": None,
                "error": None
            }
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during new code request", extra={
            "user_id": user_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Interal Server Error")


@superadmin_system_management_router.get("/dashboard-data")
async def dashboard_data(
    db : AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
):
    # user_id = 1
    user_id = user_data["user_id"]
    try:
        result = (await db.execute(
            select(AdminStats)
            .where(AdminStats.id == 1)
        )).scalar_one_or_none()
        if result is None:
            raise HTTPException(status_code=404, detail="No dashbpard data found")
        
        return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "dashboard data",
                    "data":{
                        "total_user": result.total_user,
                        "total_students": result.total_students,
                        "total_admin": result.total_admin,
                        "total_superadmins": result.total_superadmins,

                        "total_blocked_user": result.total_blocked_user,

                        "total_events": result.total_events,
                        "total_paid_events": result.total_paid_events,
                        "total_free_events": result.total_free_events,
                        "total_single_events": result.total_single_events,
                        "total_team_events": result.total_team_events,

                        "total_registration": result.total_registration,

                        "total_payments": result.total_payments,
                        "total_success_payments": result.total_success_payments,
                        "total_faild_payments": result.total_faild_payments,
                        "total_success_payment_ammount": result.total_success_payment_ammount,
                        "total_failed_payment_ammount": result.total_failed_payment_ammount
                    } ,
                    "error": None
                }
            )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("exception during new code request", extra={
            "user_id": user_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Interal Server Error")




@superadmin_system_management_router.get("/audit-logs")
async def view_audit_logs(
    user_id: int | None = Query(default=None, ge=1),
    entity_type: str | None = Query(default=None, min_length=1, max_length=50),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(15, ge=1, le=100, description="Audit logs per page"),
    db: AsyncSession = Depends(get_db),
    requesting_user: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    requesting_user_id = requesting_user["user_id"]
    try:
        filters = []
        if user_id is not None:
            filters.append(AuditLog.user_id == user_id)
        if entity_type is not None:
            filters.append(AuditLog.entity_type == entity_type.strip())

        total = await db.scalar(
            select(func.count(AuditLog.id)).where(*filters)
        )
        offset = (page - 1) * limit
        result = await db.execute(
            select(
                AuditLog.id,
                AuditLog.user_id,
                User.email.label("user_email"),
                AuditLog.action,
                AuditLog.entity_type,
                AuditLog.created_at,
            )
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(*filters)
            .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
            .offset(offset)
            .limit(limit)
        )

        logs = []
        for row in result.mappings().all():
            log = dict(row)
            log["created_at"] = log["created_at"].isoformat()
            logs.append(log)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Audit logs retrieved successfully",
                "data": {
                    "items": logs,
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": total or 0,
                        "total_pages": ((total or 0) + limit - 1) // limit,
                    },
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during audit log retrieval",
            extra={"user_id": requesting_user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@superadmin_system_management_router.get("/audit-logs/{audit_log_id:int}")
async def view_audit_log_details(
    audit_log_id: int,
    db: AsyncSession = Depends(get_db),
    requesting_user: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    requesting_user_id = requesting_user["user_id"]
    try:
        result = await db.execute(
            select(
                AuditLog.id,
                AuditLog.user_id,
                User.email.label("user_email"),
                User.role.label("user_role"),
                AuditLog.action,
                AuditLog.entity_type,
                AuditLog.entity_id,
                AuditLog.description,
                AuditLog.metadata_.label("metadata"),
                AuditLog.ip_address,
                AuditLog.user_agent,
                AuditLog.created_at,
            )
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.id == audit_log_id)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit log not found")

        audit_log = dict(row)
        audit_log["created_at"] = audit_log["created_at"].isoformat()
        if audit_log["user_role"] is not None:
            audit_log["user_role"] = audit_log["user_role"].value

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Audit log details retrieved successfully",
                "data": audit_log,
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception(
            "exception during audit log detail retrieval",
            extra={
                "audit_log_id": audit_log_id,
                "user_id": requesting_user_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")
