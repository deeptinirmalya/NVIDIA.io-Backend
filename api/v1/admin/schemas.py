from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from db.models.event import EventStatus, ParticipationType, PaymentType, PaymentScope, EventCategory, GenderType



# class AdminMessageResponse(BaseModel):
#     """Standard message response for admin operations."""
#     success: bool
#     message: str


class EventCreate(BaseModel):
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

    name: str = Field(..., min_length=3, max_length=150)
    about: str
    rules: List[str] = Field(default_factory=list)
    venue: str
    category: EventCategory
    status: EventStatus = EventStatus.DRAFT
    participation_type: ParticipationType
    payment_type: PaymentType = PaymentType.FREE
    payment_scope: Optional[PaymentScope] = None
    gender: GenderType = GenderType.BOTH
    fee: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    currency: str = "INR"
    team_size_min: Optional[int] = Field(default=None, ge=1)
    team_size_max: Optional[int] = Field(default=None, ge=1)
    max_participants: Optional[int] = Field(default=None, ge=1)
    registration_start: datetime
    registration_end: datetime
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def normalize_event_fields(self):
        if self.participation_type == ParticipationType.SINGLE:
            self.team_size_min = None
            self.team_size_max = None

        if self.payment_type == PaymentType.FREE:
            self.fee = Decimal("0")
            self.currency = "INR"
            self.payment_scope = None

        if self.payment_type == PaymentType.PAID:
            self.currency = "INR"
            if self.fee is None or self.fee <= 0:
                raise ValueError("Paid event must have a fee greater than zero")

        if self.payment_type == PaymentType.FREE and self.fee is not None and self.fee != 0:
            raise ValueError("Free event cannot have a positive fee")

        if self.team_size_max is not None and self.team_size_min is not None and self.team_size_max < self.team_size_min:
            raise ValueError("team_size_max cannot be smaller than team_size_min")

        return self

    @field_validator("team_size_max")
    @classmethod
    def validate_team_size(cls, value: Optional[int], info) -> Optional[int]:
        if value is not None:
            minimum = info.data.get("team_size_min")
            if minimum is not None and value < minimum:
                raise ValueError("team_size_max cannot be smaller than team_size_min")
        return value

    @field_validator("payment_scope")
    @classmethod
    def validate_payment_scope(cls, value: Optional[PaymentScope], info) -> Optional[PaymentScope]:
        payment_type = info.data.get("payment_type")
        participation_type = info.data.get("participation_type")

        if payment_type == PaymentType.FREE and value is not None:
            raise ValueError("payment_scope must be None for free events")

        if (
            payment_type == PaymentType.PAID
            and participation_type == ParticipationType.TEAM
            and value is None
        ):
            raise ValueError("payment_scope is required for paid team events")
        return value

    @field_validator("fee")
    @classmethod
    def validate_fee(cls, value: Optional[Decimal], info) -> Optional[Decimal]:
        payment_type = info.data.get("payment_type")

        if payment_type == PaymentType.PAID:
            if value is None or value <= 0:
                raise ValueError("Paid event must have a fee greater than zero")

        if payment_type == PaymentType.FREE:
            if value is not None and value != 0:
                raise ValueError("Free event cannot have a positive fee")
        return value

