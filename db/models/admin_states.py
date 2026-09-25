from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class AdminStats(Base):
    __tablename__ = "admin_stats"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    total_user: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_admin: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_superadmins: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    total_events: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_paid_events: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_free_events: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_single_events: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_team_events: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    total_registration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    total_payments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_success_payments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_faild_payments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_success_payment_ammount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    total_failed_payment_ammount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
