from upstash_redis.asyncio import Redis
import json

from core.config import settings

# Initialize Upstash Redis Cache via REST (HTTP)
# This requires the 'upstash-redis' library
redis_client = Redis(
    url=settings.UPSTASH_REDIS_REST_URL, 
    token=settings.UPSTASH_REDIS_REST_TOKEN
)


async def set_value(key: str, value, expire: int = 3600):
    await redis_client.set(
        key,
        json.dumps(value),
        ex=expire
    )


async def get_value(key: str):
    value = await redis_client.get(key)

    if value is None:
        return None

    return json.loads(value)


async def delete_value(key: str):
    await redis_client.delete(key)
