from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class EmailLogStatus(str, PyEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class EmailLog(Base):
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    sender_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[EmailLogStatus] = mapped_column(
        Enum(EmailLogStatus, name="email_log_status_enum"),
        nullable=False,
        default=EmailLogStatus.PENDING,
    )

    provider_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    recipient_count_details: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
