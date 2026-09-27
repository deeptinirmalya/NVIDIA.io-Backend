import logging

from engine.cache import redis_client

logger = logging.getLogger("bloomfilter")

EVENT_BLOOM_KEY = "event_ids_bloom"
EVENT_BLOOM_ERROR_RATE = 0.01
EVENT_BLOOM_CAPACITY = 250


async def ensure_event_bloom() -> None:
    try:
        await redis_client.execute_command("BF.INFO", EVENT_BLOOM_KEY)
        return
    except Exception:
        pass

    try:
        await redis_client.execute_command(
            "BF.RESERVE",
            EVENT_BLOOM_KEY,
            str(EVENT_BLOOM_ERROR_RATE),
            str(EVENT_BLOOM_CAPACITY),
        )
    except Exception:
        logger.warning(
            "RedisBloom not available or not initialized; event bloom check will be skipped.",
            extra={"bloom_key": EVENT_BLOOM_KEY},
        )


async def add_event_id_to_bloom(event_id: int) -> bool:
    if event_id is None:
        return False

    try:
        await ensure_event_bloom()
        await redis_client.execute_command("BF.ADD", EVENT_BLOOM_KEY, f"event:{event_id}")
        return True
    except Exception:
        logger.exception("Failed to add event ID to bloom filter", extra={"event_id": event_id})
        return False


async def event_id_exists_in_bloom(event_id: int) -> bool:
    if event_id is None:
        return False

    try:
        await ensure_event_bloom()
        result = await redis_client.execute_command("BF.EXISTS", EVENT_BLOOM_KEY, f"event:{event_id}")
        return bool(result)
    except Exception:
        return True
