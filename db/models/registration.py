from datetime import datetime
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class RegistrationType(str, Enum):
    SINGLE = "SINGLE"
    TEAM = "TEAM"


class RegistrationStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class RegistrationPaymentStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Registration(Document):

    event_id: PydanticObjectId

    registration_type: RegistrationType

    # --------------------------------------------------------
    # SINGLE EVENT
    # --------------------------------------------------------

    user_id: PydanticObjectId | None = None

    # --------------------------------------------------------
    # TEAM EVENT
    # --------------------------------------------------------

    team_id: PydanticObjectId | None = None

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    status: RegistrationStatus = RegistrationStatus.PENDING

    payment_status: RegistrationPaymentStatus = (
        RegistrationPaymentStatus.NOT_REQUIRED
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    class Settings:

        name = "registrations"

        indexes = [

            # One user can register only once
            # for a single event.
            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("user_id", ASCENDING)
                ],
                unique=True,
                partialFilterExpression={
                    "user_id": {"$exists": True}
                }
            ),

            # One team can have only one registration
            # for an event.
            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("team_id", ASCENDING)
                ],
                unique=True,
                partialFilterExpression={
                    "team_id": {"$exists": True}
                }
            ),

            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("status", ASCENDING)
                ]
            ),

            IndexModel(
                [
                    ("user_id", ASCENDING),
                    ("status", ASCENDING)
                ]
            ),

            IndexModel(
                [("created_at", DESCENDING)]
            ),
        ]