import logging

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from core.config import settings

logger = logging.getLogger("bloomfilter")

EVENT_BLOOM_KEY = "event_ids_bloom"
EVENT_BLOOM_ERROR_RATE = 0.01
EVENT_BLOOM_CAPACITY = 250

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def ensure_event_bloom() -> None:
    try:
        await redis_client.execute_command(
            "BF.RESERVE",
            EVENT_BLOOM_KEY,
            EVENT_BLOOM_ERROR_RATE,
            EVENT_BLOOM_CAPACITY,
        )
        logger.info("Bloom filter created", extra={"filter_name": EVENT_BLOOM_KEY})
    except ResponseError as exc:
        if "item exists" in str(exc).lower():
            logger.info("Bloom filter already exists", extra={"filter_name": EVENT_BLOOM_KEY})
            return
        raise


async def close_event_bloom() -> None:
    await redis_client.aclose()


async def add_event_id_to_bloom(event_id: int) -> bool:
    if event_id is None:
        return False

    try:
        result = await redis_client.execute_command(
            "BF.ADD", EVENT_BLOOM_KEY, f"event:{event_id}"
        )
        return result == 1
    except Exception:
        logger.exception("Failed to add event ID to bloom filter", extra={"event_id": event_id})
        return False


async def event_id_exists_in_bloom(event_id: int) -> bool:
    if event_id is None:
        return False

    try:
        result = await redis_client.execute_command(
            "BF.EXISTS", EVENT_BLOOM_KEY, f"event:{event_id}"
        )
        return result == 1
    except Exception:
        return True
