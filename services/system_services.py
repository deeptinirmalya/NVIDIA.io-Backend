import logging

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from db.models.system_setting import SystemSetting
from db.session import AsyncSessionLocal
from engine.cache import KEY_FOR_MAINTENENACE, get_value, set_value
from utils.auth_util import get_now_utc

logger = logging.getLogger(__name__)


async def ensure_maintenance_setting() -> None:
	async with AsyncSessionLocal() as session:
		insert_statement = mysql_insert(SystemSetting).values(
			setting_key=KEY_FOR_MAINTENENACE,
			toggle_on=False,
			created_at=get_now_utc(),
		)
		statement = insert_statement.on_duplicate_key_update(
			setting_key=insert_statement.inserted.setting_key
		)
		await session.execute(statement)
		await session.commit()


async def get_setting_toggle(setting_key: str) -> bool | None:
	try:
		cached_value = await get_value(setting_key)
		if cached_value is not None:
			return cached_value
	except Exception:
		logger.warning(
			"Unable to read system setting from cache; falling back to database",
			extra={"setting_key": setting_key},
			exc_info=True,
		)

	try:
		async with AsyncSessionLocal() as session:
			setting = await session.scalar(
				select(SystemSetting).where(SystemSetting.setting_key == setting_key)
			)
	except Exception:
		logger.exception(
			"Unable to read system setting from database",
			extra={"setting_key": setting_key},
		)
		raise

	if setting is None:
		return None

	toggle_value = setting.toggle_on
	if toggle_value is not None:
		try:
			await set_value(setting_key, toggle_value, None)
		except Exception:
			logger.warning(
				"Unable to cache system setting retrieved from database",
				extra={"setting_key": setting_key},
				exc_info=True,
			)

	return toggle_value

