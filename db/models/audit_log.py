from datetime import datetime

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class AuditLog(Document):

    actor_user_id: PydanticObjectId | None = None

    action: str

    entity_type: str

    entity_id: PydanticObjectId

    metadata: dict = Field(
        default_factory=dict
    )

    ip_address: str | None = None

    user_agent: str | None = None

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    class Settings:

        name = "audit_logs"

        indexes = [

            IndexModel(
                [
                    ("entity_type", ASCENDING),
                    ("entity_id", ASCENDING)
                ]
            ),

            IndexModel(
                [
                    ("actor_user_id", ASCENDING),
                    ("created_at", DESCENDING)
                ]
            ),

            IndexModel(
                [("created_at", DESCENDING)]
            ),
        ]