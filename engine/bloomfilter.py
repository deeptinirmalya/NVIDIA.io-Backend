import logging

from engine.cache import redis_client

logger = logging.getLogger("bloomfilter")

EVENT_BLOOM_KEY = "event_ids_bloom"
EVENT_BLOOM_ERROR_RATE = 0.01
EVENT_BLOOM_CAPACITY = 250


async def ensure_event_bloom() -> None:
    # Not required for standard Redis sets.
    pass


async def add_event_id_to_bloom(event_id: int) -> bool:
    if event_id is None:
        return False

    try:
        await redis_client.sadd(EVENT_BLOOM_KEY, f"event:{event_id}")
        return True
    except Exception:
        logger.exception("Failed to add event ID to bloom filter", extra={"event_id": event_id})
        return False


async def event_id_exists_in_bloom(event_id: int) -> bool:
    if event_id is None:
        return False

    try:
        result = await redis_client.sismember(EVENT_BLOOM_KEY, f"event:{event_id}")
        return bool(result)
    except Exception:
        return True
