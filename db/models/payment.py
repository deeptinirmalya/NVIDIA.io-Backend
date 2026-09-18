from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Boolean,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class PaymentParticipationType(str, PyEnum):
    SINGLE = "SINGLE"
    TEAM = "TEAM"


class PaymentStatus(str, PyEnum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class FirstCame(str, PyEnum):
    FRONTEND = "FRONTEND"
    WEBHOOK = "WEBHOOK"



class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint(
            "("
            "participation_type = 'SINGLE' "
            "AND single_registration_id IS NOT NULL "
            "AND team_registration_id IS NULL"
            ") "
            "OR "
            "("
            "participation_type = 'TEAM' "
            "AND team_registration_id IS NOT NULL "
            "AND single_registration_id IS NULL"
            ")",
            name="check_payment_participation_type",
        ),
        CheckConstraint(
            "("
            "single_registration_id IS NOT NULL "
            "AND team_registration_id IS NULL"
            ") "
            "OR "
            "("
            "single_registration_id IS NULL "
            "AND team_registration_id IS NOT NULL"
            ")",
            name="check_payment_single_or_team",
        ),
        Index(
            "idx_payment_single_reg_status",
            "single_registration_id",
            "status",
        ),
        Index(
            "idx_payment_team_reg_status",
            "team_registration_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    participation_type: Mapped[PaymentParticipationType] = mapped_column(
        Enum(PaymentParticipationType, name="payment_participation_type_enum"),
        nullable=False,
        default=PaymentParticipationType.SINGLE,
    )

    single_registration_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "single_registrations.id",
            ondelete="RESTRICT",
            name="fk_payment_single_registration",
        ),
        nullable=True,
    )

    team_registration_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "team_registrations.id",
            ondelete="RESTRICT",
            name="fk_payment_team_registration",
        ),
        nullable=True,
    )

    amount: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="INR",
    )

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum"),
        nullable=False,
        default=PaymentStatus.CREATED,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    razorpay_order_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )

    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )

    razorpay_signature: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    signature_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    first_came: Mapped[FirstCame] = mapped_column(
        Enum(FirstCame, name="first_came"),
        nullable=True
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    gateway_error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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