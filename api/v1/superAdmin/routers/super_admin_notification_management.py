import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, asc, func

from db.session import get_db
from security.auth import token_required
from security.rate_limiter import rate_limiter
from utils import auth_util, util
from templates.srjn_email_templete import build_email_html


from db.models.auth import User
from db.models.email_log import EmailLog, EmailLogStatus


from ..schemas import EmailSentRequest
from ..others import verify_superadmin_code

import services.count_service as cServices
from services.auditlog_service import create_audit_log

logger = logging.getLogger("Super-admin-notification-Management")


superadmin_notification_management_router = APIRouter()


@superadmin_notification_management_router.post("/send-email")
async def send_email(
    data: EmailSentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_data: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=1, refill_rate=0.1, mode="both"))
):
    try:
        priority = None
        match data.notification_type:
            case "ANNOUNCEMENT":
                priority = 3
            case "INFORMATION":
                priority = 6
            case "IMPORTANT":
                priority = 9
            case "REMINDER":
                priority = 8
            case _:
                priority = 5

        receiver_count = len(data.receiver_emails)
        cc = len(data.cc_emails) if data.cc_emails else 0
        bcc = len(data.bcc_emails) if data.bcc_emails else 0
        total_recipients = receiver_count + cc + bcc

        if total_recipients > 500:
            raise HTTPException(status_code=409, detail="For now only max 500 emails are allowed per day including CC and BCC.")

        body = build_email_html(data)

        new_email_logs = EmailLog(
            sender_id=user_data["user_id"],
            subject=data.subject,
            email_type=data.notification_type,
            status=EmailLogStatus.SENT,
            recipient_count_details=f"RECEIVER:- {receiver_count} || CC:- {cc} || BCC:- {bcc}",
            created_at=auth_util.get_now_utc(),
            sent_at=auth_util.get_now_utc()
        )
        db.add(new_email_logs)
        await db.flush()

        await util.mail_service(
            subject=data.subject,
            body=body,
            receiver_email=data.receiver_emails,
            cc_emails=data.cc_emails,
            bcc_emails=data.bcc_emails,
            priority = priority
        )
        await db.commit()

        await create_audit_log(
            request=request,
            user_id=user_data["user_id"],
            action="SENT_MAIL",
            entity_type="MAIL",
            entity_id=new_email_logs.id,
            description="New mail Sent by superadmin",
            metadata={"subject": data.subject}
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Mail queued successfully",
                "data": None,
                "error": None
            }
        )
    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        logger.exception("Exceptio during send Email", extra={
            "superdmin_id": user_data["user_id"],
            "subject": data.subject,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="internal server error")

@superadmin_notification_management_router.get("/email-logs")
async def get_email_logs(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(15, ge=1, le=15, description="Email logs per page"),
    status: str | None = Query(default=None, min_length=1, max_length=20),
    email_type: str | None = Query(default=None, min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db),
    requesting_user: dict = Depends(token_required(allowed_roles=["SUPERADMIN"])),
    _ = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    requesting_user_id = requesting_user["user_id"]
    try:
        filters = []
        if status is not None:
            filters.append(EmailLog.status == status.strip().upper())
        if email_type is not None:
            filters.append(EmailLog.email_type == email_type.strip())

        total = await db.scalar(
            select(func.count(EmailLog.id)).where(*filters)
        )
        offset = (page - 1) * limit

        result = await db.execute(
            select(
                EmailLog.id,
                User.email.label("sender_email"),
                EmailLog.subject,
                EmailLog.email_type,
                EmailLog.status,
                EmailLog.created_at,
                EmailLog.sent_at,
                EmailLog.recipient_count_details,
            )
            .outerjoin(User, User.id == EmailLog.sender_id)
            .where(*filters)
            .order_by(desc(EmailLog.created_at), desc(EmailLog.id))
            .offset(offset)
            .limit(limit)
        )

        items = []
        for row in result.mappings().all():
            data_row = dict(row)
            if data_row.get("created_at") is not None:
                data_row["created_at"] = data_row["created_at"].isoformat()
            if data_row.get("sent_at") is not None:
                data_row["sent_at"] = data_row["sent_at"].isoformat()
            items.append(data_row)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Email logs retrieved successfully",
                "data": {
                    "items": items,
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
            "exception during email log retrieval",
            extra={"user_id": requesting_user_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")