from upstash_redis import Redis
from core.config import settings

# Initialize Upstash Redis Cache via REST (HTTP)
# This requires the 'upstash-redis' library
redis_client = Redis(
    url=settings.UPSTASH_REDIS_REST_URL, 
    token=settings.UPSTASH_REDIS_REST_TOKEN
)

def set_value(key: str, value: str, expire: int = 3600):
    redis_client.set(key, value, ex=expire)

def get_value(key: str):
    return redis_client.get(key)
