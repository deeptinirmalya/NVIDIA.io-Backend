from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator, ConfigDict


class EventStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REGISTRATION_CLOSED = "REGISTRATION_CLOSED"


class ParticipationType(str, Enum):
    SINGLE = "SINGLE"
    TEAM = "TEAM"


class PaymentType(str, Enum):
    FREE = "FREE"
    PAID = "PAID"


class PaymentScope(str, Enum):
    SINGLE = "SINGLE"
    TEAM = "TEAM"


class EventCategory(str, Enum):
    TECH = "TECH"
    NON_TECH = "NON_TECH"
    CULTURAL = "CULTURAL"
    SPORTS = "SPORTS"
    ESPORTS = "ESPORTS"


class GenderType(str, Enum):
    BOYS = "BOYS"
    GIRLS = "GIRLS"
    BOTH = "BOTH"


class EventCreate(BaseModel):

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    about: str | None = None

    rules: str | None = None

    venue: str | None = Field(
        default=None,
        max_length=200,
    )

    registration_start_time: datetime

    registration_end_time: datetime 

    event_start_time: datetime | None = None

    event_end_time: datetime | None = None

    status: EventStatus = EventStatus.DRAFT

    participation_type: ParticipationType = (
        ParticipationType.SINGLE
    )

    category: EventCategory = EventCategory.TECH

    gender_type: GenderType = GenderType.BOTH

    is_paid: bool = False

    price: int = Field(
        default=0,
        ge=0,
    )

    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
    )

    min_team_size: int | None = Field(
        default=None,
        ge=1,
    )

    max_team_size: int | None = Field(
        default=None,
        ge=1,
    )

    banner: str  # Base64 image

    @model_validator(mode="after")
    def validate_event(self):

        if not self.is_paid and self.price != 0:
            raise ValueError(
                "price must be 0 when is_paid is False"
            )

        if self.is_paid and self.price <= 0:
            raise ValueError(
                "price must be greater than 0 when is_paid is True"
            )

        if self.currency != "INR":
            raise ValueError(
                "currency must be INR"
            )

        if self.participation_type == ParticipationType.SINGLE:

            if (
                self.min_team_size is not None
                or self.max_team_size is not None
            ):
                raise ValueError(
                    "min_team_size and max_team_size "
                    "must be null for SINGLE events"
                )

        elif self.participation_type == ParticipationType.TEAM:

            if self.min_team_size is None:
                raise ValueError(
                    "min_team_size is required for TEAM events"
                )

            if self.max_team_size is None:
                raise ValueError(
                    "max_team_size is required for TEAM events"
                )

            if self.max_team_size < self.min_team_size:
                raise ValueError(
                    "max_team_size must be greater than "
                    "or equal to min_team_size"
                )

        if (
            self.registration_end_time is not None
            and self.registration_end_time
            < self.registration_start_time
        ):
            raise ValueError(
                "registration_end_time cannot be before "
                "registration_start_time"
            )

        if (
            self.registration_end_time is not None
            and self.event_start_time is not None
            and self.registration_end_time
            > self.event_start_time
        ):
            raise ValueError(
                "registration_end_time cannot be after "
                "event_start_time"
            )

        if (
            self.event_end_time is not None
            and self.event_start_time is not None
            and self.event_end_time
            < self.event_start_time
        ):
            raise ValueError(
                "event_end_time cannot be before "
                "event_start_time"
            )

        return self


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    about: str | None = None
    rules: str | None = Field(default=None, max_length=500)
    venue: str | None = Field(default=None, max_length=200)
    registration_start_time: datetime | None = None
    registration_end_time: datetime | None = None
    event_start_time: datetime | None = None
    event_end_time: datetime | None = None
    status: EventStatus | None = None
    participation_type: ParticipationType | None = None
    category: EventCategory | None = None
    gender_type: GenderType | None = None
    is_paid: bool | None = None
    price: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    min_team_size: int | None = Field(default=None, ge=1)
    max_team_size: int | None = Field(default=None, ge=1)
    banner: str | None = None


class EventAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    about: str | None
    rules: str | None
    venue: str | None
    registration_start_time: datetime
    registration_end_time: datetime | None
    event_start_time: datetime | None
    event_end_time: datetime | None
    status: EventStatus
    participation_type: ParticipationType
    category: EventCategory
    gender_type: GenderType
    is_paid: bool
    price: int
    currency: str
    min_team_size: int | None
    max_team_size: int | None
    banner_url: str | None
    created_at: datetime
    updated_at: datetime | None



from pydantic import BaseModel, EmailStr, Field


class NewSuperAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=8)
    code: int = Field(ge=100000, le=999999)