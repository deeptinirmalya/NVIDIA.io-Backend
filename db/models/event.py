from datetime import datetime
from decimal import Decimal
from enum import Enum

from beanie import Document, PydanticObjectId
from bson.decimal128 import Decimal128
from pydantic import Field, field_validator
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.collation import Collation

class EventStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ParticipationType(str, Enum):
    SINGLE = "SINGLE"
    TEAM = "TEAM"


class PaymentType(str, Enum):
    FREE = "FREE"
    PAID = "PAID"


class PaymentScope(str, Enum):

    TEAM = "TEAM"
    PARTICIPANT = "PARTICIPANT"


class EventCategory(str, Enum):
    TECH = "TECH"
    NON_TECH = "NON_TECH"
    SPORTS = "SPORTS"
    CULTURAL = "CULTURAL"


class GenderType(str, Enum):
    BOYS = "BOYS"
    GIRLS = "GIRLS"
    BOTH = "BOTH"


class Event(Document):

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        if isinstance(value, str):
            normalized = value.strip().upper().replace(" ", "_").replace("-", "_")
            alias_map = {
                "NONTECH": "NON_TECH",
                "CULTURE": "CULTURAL",
                "CULTURAL": "CULTURAL",
            }
            return alias_map.get(normalized, normalized)
        return value

    name: str = Field(min_length=3, max_length=150)

    about: str
    rules: list[str] = Field(default_factory=list)

    venue: str

    category: EventCategory

    status: EventStatus = EventStatus.DRAFT

    participation_type: ParticipationType

    payment_type: PaymentType = PaymentType.FREE

    payment_scope: PaymentScope | None = None

    gender: GenderType = GenderType.BOTH

    fee: Decimal | None = Field(
        default=None,
        ge=Decimal("0")
    )

    currency: str = "INR"

    team_size_min: int | None = Field(
        default=None,
        ge=1
    )

    team_size_max: int | None = Field(
        default=None,
        ge=1
    )


    max_participants: int | None = Field(
        default=None,
        ge=1
    )

    registration_start: datetime
    registration_end: datetime

    start_time: datetime
    end_time: datetime

    created_by: str

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )



    @field_validator("team_size_max")
    @classmethod
    def validate_team_size(
        cls,
        value: int | None,
        info
    ):
        if value is not None:
            minimum = info.data.get("team_size_min")

            if minimum is not None and value < minimum:
                raise ValueError(
                    "team_size_max cannot be smaller than team_size_min"
                )

        return value

    @field_validator("payment_scope")
    @classmethod
    def validate_payment_scope(
        cls,
        value: PaymentScope | None,
        info
    ):
        payment_type = info.data.get("payment_type")
        participation_type = info.data.get("participation_type")

        if payment_type == PaymentType.FREE and value is not None:
            raise ValueError(
                "payment_scope must be None for free events"
            )

        if (
            payment_type == PaymentType.PAID
            and participation_type == ParticipationType.TEAM
            and value is None
        ):
            raise ValueError(
                "payment_scope is required for paid team events"
            )

        return value

    @field_validator("fee", mode="before")
    @classmethod
    def normalize_fee(cls, value):
        if value is None:
            return value
        if isinstance(value, Decimal128):
            return value.to_decimal()
        if isinstance(value, (int, float, str, Decimal)):
            return Decimal(str(value))
        return value

    @field_validator("fee")
    @classmethod
    def validate_fee(
        cls,
        value: Decimal | None,
        info
    ):
        payment_type = info.data.get("payment_type")

        if payment_type == PaymentType.PAID:
            if value is None or value <= 0:
                raise ValueError(
                    "Paid event must have a fee greater than zero"
                )

        if payment_type == PaymentType.FREE:
            if value is not None and value != 0:
                raise ValueError(
                    "Free event cannot have a positive fee"
                )

        return value

    class Settings:
        name = "events"
        indexes = [
            IndexModel(
                [
                    ("status", ASCENDING),
                    ("registration_start", ASCENDING)
                ]
            ),
            IndexModel(
                [("start_time", ASCENDING)]
            ),

            IndexModel(
                [("created_at", DESCENDING)]
            ),

            IndexModel(
                [
                    ("category", ASCENDING),
                    ("status", ASCENDING)
                ]
            ),
        ]