from upstash_redis.asyncio import Redis
import json
import uuid

from core.config import settings


# from redis.asyncio import Redis

# redis_client = Redis(
#     host="127.0.0.1",
#     port=6379,
#     decode_responses=True
# )

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



#  ---------------- PAYMENT LOCK ----------------

async def acquire_payment_lock(payment_id: int, expire: int = 10):
    lock_key = f"payment_lock:{payment_id}"
    lock_token = str(uuid.uuid4())

    acquired = await redis_client.set(
        lock_key,
        lock_token,
        nx=True,
        ex=expire
    )

    if not acquired:
        return None, lock_key

    return lock_token, lock_key


async def release_payment_lock(lock_key: str, lock_token: str):
    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """

    await redis_client.eval(
        lua_script,
        keys=[lock_key],
        args=[lock_token],
    )
