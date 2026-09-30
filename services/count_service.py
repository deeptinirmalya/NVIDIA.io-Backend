from __future__ import annotations

from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.admin_states import AdminStats


async def _ensure_stats_row(db: AsyncSession) -> None:
    row = await db.scalar(select(AdminStats).where(AdminStats.id == 1))
    if row is None:
        db.add(AdminStats(id=1))
        await db.flush()

# ======================= USER SECTION ===============================================

async def increase_user_count(db: AsyncSession) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_user=AdminStats.total_user + 1)
    )
    await db.commit()

    return


async def increase_student_count(db: AsyncSession) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_students=AdminStats.total_students + 1)
    )

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_user=AdminStats.total_user + 1)
    )
    await db.commit()

    return True


async def increase_admin_count(db: AsyncSession) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_admin=AdminStats.total_admin + 1)
    )

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_user=AdminStats.total_user + 1)
    )
    await db.commit()

    return True


async def increase_superadmin_count(db: AsyncSession) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_superadmins=AdminStats.total_superadmins + 1)
    )

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_user=AdminStats.total_user + 1)
    )
    await db.commit()

    return True

async def increase_decrease_blocked_count(db: AsyncSession, is_block: bool) -> int:
    await _ensure_stats_row(db)

    if not is_block:
        await db.execute(
            update(AdminStats)
            .where(AdminStats.id == 1)
            .values(total_blocked_user=AdminStats.total_blocked_user - 1)
        )
    else:
        await db.execute(
            update(AdminStats)
            .where(AdminStats.id == 1)
            .values(total_blocked_user=AdminStats.total_blocked_user + 1)
        )

    await db.commit()

    return True

# ======================= USER SECTION ===============================================


# ======================= EVENT SECTION ===============================================



async def increase_event_count(
    db: AsyncSession,
    amount: int = 1,
    *,
    event_type: Literal["single", "team"] | None = None,
    is_paid: bool | None = None,
) -> int:
    amount = int(amount)
    await _ensure_stats_row(db)

    updates = {"total_events": AdminStats.total_events + amount}

    if is_paid is True:
        updates["total_paid_events"] = AdminStats.total_paid_events + amount
    elif is_paid is False:
        updates["total_free_events"] = AdminStats.total_free_events + amount

    if event_type == "single":
        updates["total_single_events"] = AdminStats.total_single_events + amount
    elif event_type == "team":
        updates["total_team_events"] = AdminStats.total_team_events + amount

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(**updates)
    )
    await db.commit()

    updated_total = await db.scalar(
        select(AdminStats.total_events).where(AdminStats.id == 1)
    )
    return int(updated_total or 0)

# ======================= EVENT SECTION ===============================================

# ================================= PAYMNET SECTION ===============================
async def increase_total_success_payment_count(db: AsyncSession, amount) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_success_payments=AdminStats.total_success_payments + 1,
                total_success_payment_ammount = AdminStats.total_success_payment_ammount + amount)
    )

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_payments=AdminStats.total_payments + 1)
    )
    await db.commit()

    return True


async def increase_total_failed_payment_count(db: AsyncSession, amount) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_faild_payments=AdminStats.total_faild_payments + 1,
                total_failed_payment_ammount = AdminStats.total_failed_payment_ammount + amount)
    )

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_payments=AdminStats.total_payments + 1)
    )
    await db.commit()

    return True


#================= registration section ====================================

async def increase_total_registration_count(db: AsyncSession, amount: int = 1) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_registration=AdminStats.total_registration + amount)
    )

    await db.commit()

    return True


async def decrease_total_registration_count(db: AsyncSession, amount: int = 1) -> int:
    await _ensure_stats_row(db)

    await db.execute(
        update(AdminStats)
        .where(AdminStats.id == 1)
        .values(total_registration=AdminStats.total_registration - amount)
    )

    await db.commit()

    return True
