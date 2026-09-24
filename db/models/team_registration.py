from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class TeamStatus(str, PyEnum):
    FORMING = "FORMING"
    FULL = "FULL"
    ELIGIBLE = "ELIGIBLE"


class TeamRegistrationStatus(str, PyEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class TeamRegistrationPaymentStatus(str, PyEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class TeamRegistration(Base):
    __tablename__ = "team_registrations"

    __table_args__ = (
        Index(
            "idx_team_registration_event_status",
            "event_id",
            "status",
        ),
        Index(
            "idx_team_registration_captain",
            "captain_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "events.id",
            ondelete="RESTRICT",
            name="fk_team_registration_event",
        ),
        nullable=False,
    )

    team_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    team_code: Mapped[str] = mapped_column(
        String(8),
        unique=True,
        nullable=False,
    )

    captain_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_team_registration_captain",
        ),
        nullable=False,
    )

    team_status: Mapped[TeamStatus] = mapped_column(
        Enum(TeamStatus, name="team_status_enum"),
        nullable=False,
        default=TeamStatus.FORMING,
    )

    status: Mapped[TeamRegistrationStatus] = mapped_column(
        Enum(TeamRegistrationStatus, name="team_registration_status_enum"),
        nullable=False,
        default=TeamRegistrationStatus.PENDING,
    )

    payment_status: Mapped[TeamRegistrationPaymentStatus] = mapped_column(
        Enum(
            TeamRegistrationPaymentStatus,
            name="team_registration_payment_status_enum",
        ),
        nullable=False,
        default=TeamRegistrationPaymentStatus.NOT_REQUIRED,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )