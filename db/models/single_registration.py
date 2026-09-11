from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class SingleRegistrationStatus(str, PyEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class SingleRegistrationPaymentStatus(str, PyEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class SingleRegistration(Base):
    __tablename__ = "single_registrations"

    __table_args__ = (
        Index(
            "idx_single_registration_event_status",
            "event_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "events.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    status: Mapped[SingleRegistrationStatus] = mapped_column(
        Enum(SingleRegistrationStatus, name="single_registration_status_enum"),
        nullable=False,
        default=SingleRegistrationStatus.PENDING,
    )

    payment_status: Mapped[SingleRegistrationPaymentStatus] = mapped_column(
        Enum(
            SingleRegistrationPaymentStatus,
            name="single_registration_payment_status_enum",
        ),
        nullable=False,
        default=SingleRegistrationPaymentStatus.NOT_REQUIRED,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )