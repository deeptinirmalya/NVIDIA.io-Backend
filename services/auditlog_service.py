import logging
from collections.abc import Mapping
from typing import Any

from fastapi import Request

from db.models.audit_log import AuditLog
from db.session import AsyncSessionLocal
from utils.auth_util import get_now_utc

from dependences.dependency import get_client_ip, get_user_agent


logger = logging.getLogger("auditlog_service")


async def create_audit_log(
    *,
    request: Request,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    description: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> int | None:
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        metadata_=dict(metadata) if metadata is not None else None,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        created_at=get_now_utc(),
    )

    try:
        async with AsyncSessionLocal() as session:
            session.add(audit_log)
            await session.commit()
            return audit_log.id
    except Exception:
        logger.exception(
            "Failed to create audit log",
            extra={
                "user_id": user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
        )
        return None