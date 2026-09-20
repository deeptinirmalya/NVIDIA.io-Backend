from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class EventStatus(str, PyEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REGISTRATION_CLOSED = "REGISTRATION_CLOSED"


class ParticipationType(str, PyEnum):
    SINGLE = "SINGLE"
    TEAM = "TEAM"


class PaymentType(str, PyEnum):
    FREE = "FREE"
    PAID = "PAID"


class PaymentScope(str, PyEnum):
    SINGLE = "SINGLE"
    TEAM = "TEAM"


class EventCategory(str, PyEnum):
    TECH = "TECH"
    NON_TECH = "NON_TECH"
    CULTURAL = "CULTURAL"
    SPORTS = "SPORTS"
    ESPORTS = "ESPORTS"


class GenderType(str, PyEnum):
    BOYS = "BOYS"
    GIRLS = "GIRLS"
    BOTH = "BOTH"


class Event(Base):
    __tablename__ = "events"

    __table_args__ = (
        CheckConstraint(
            "(is_paid = FALSE AND price = 0) "
            "OR (is_paid = TRUE AND price > 0)",
            name="check_event_price",
        ),
        CheckConstraint(
            "("
            "participation_type = 'SINGLE' "
            "AND min_team_size IS NULL "
            "AND max_team_size IS NULL"
            ") "
            "OR "
            "("
            "participation_type = 'TEAM' "
            "AND min_team_size IS NOT NULL "
            "AND max_team_size IS NOT NULL "
            "AND min_team_size > 0 "
            "AND max_team_size >= min_team_size"
            ")",
            name="check_event_team_size",
        ),
        CheckConstraint(
            "registration_end_time IS NULL "
            "OR registration_end_time >= registration_start_time",
            name="check_event_registration_time",
        ),
        CheckConstraint(
            "registration_end_time IS NULL "
            "OR event_start_time IS NULL "
            "OR registration_end_time <= event_start_time",
            name="check_event_registration_before_event",
        ),
        CheckConstraint(
            "event_end_time IS NULL "
            "OR event_start_time IS NULL "
            "OR event_end_time >= event_start_time",
            name="check_event_time",
        ),
        CheckConstraint(
            "currency = 'INR'",
            name="check_event_currency",
        ),
        Index("idx_events_status", "status"),
        Index("idx_events_type", "participation_type"),
        Index("idx_events_start_time", "event_start_time"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
    )

    about: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rules: Mapped[str | None] = mapped_column(
        String(500),
        nullable=False,
    )

    venue: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    registration_start_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    registration_end_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    event_start_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    event_end_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status_enum"),
        nullable=False,
        default=EventStatus.DRAFT,
    )

    participation_type: Mapped[ParticipationType] = mapped_column(
        Enum(ParticipationType, name="participation_type_enum"),
        nullable=False,
        default=ParticipationType.SINGLE,
    )

    category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, name="event_category_enum"),
        nullable=False,
        default=EventCategory.TECH,
    )

    gender_type: Mapped[GenderType] = mapped_column(
        Enum(GenderType, name="gender_type_enum"),
        nullable=False,
        default=GenderType.BOTH,
    )

    is_paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    price: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        nullable=False,
        default=0,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    min_team_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    max_team_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    banner_url: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )