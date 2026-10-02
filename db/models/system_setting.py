from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    setting_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    toggle_on: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
        server_default="0",
    )
    key_value: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )