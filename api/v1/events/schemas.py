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












# ==================================== RESPONSE FORMAT =============================

class EventResponse(BaseModel):
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


    min_team_size: int | None
    max_team_size: int | None
