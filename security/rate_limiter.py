import time
import json
import logging
from typing import Callable, Awaitable, Optional

import redis
from fastapi import Request, HTTPException, Depends

from core.config import settings
from dependences.dependency import get_client_ip


try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_timeout=1,
        socket_connect_timeout=1,
    )
except Exception as exc:
    logging.error(f"⚠️ Rate‑limiter: Redis connection failed – {exc}")
    redis_client = None


LUA_SCRIPT = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call("HMGET", key, "tokens", "timestamp")
local tokens = tonumber(data[1])
local last_time = tonumber(data[2])

if tokens == nil then
    tokens = max_tokens
    last_time = now
end

local delta = math.max(0, now - last_time)
local refill = delta * refill_rate
tokens = math.min(max_tokens, tokens + refill)

if tokens < 1 then
    return {0, tostring(tokens)}
end

tokens = tokens - 1
redis.call("HSET", key, "tokens", tokens, "timestamp", now)
redis.call("EXPIRE", key, 120)
return {1, tostring(tokens)}
"""

rate_limiter_script = (
    redis_client.register_script(LUA_SCRIPT) if redis_client else None
)


TRUSTED_PROXIES = getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1"])

def rate_limiter(
    max_tokens: int = 10,
    refill_rate: float = 1.0,
    mode: str = "both",
    *,
    on_block: Optional[Callable[[Request, str], Awaitable[None]]] = None,
) -> Callable[[Request], Awaitable[None]]:
    if mode not in {"ip", "user", "both", "login"}:
        raise ValueError(f'Invalid mode="{mode}". Expected one of ip,user,both,login.')

    async def limiter(request: Request) -> None:

        if not redis_client or not rate_limiter_script:
            logging.error("Rate‑limiter invoked while Redis is unavailable")
            raise HTTPException(
                status_code=503,
                detail="Rate‑limiting service unavailable – please try again later",
            )


        now = int(time.time())
        keys: list[str] = []

        client_ip = get_client_ip(request)

        if mode in ("ip", "both", "login"):
            keys.append(f"rate:ip:{client_ip}")

        if mode in ("user", "both") and hasattr(request.state, "user"):
            user_data = request.state.user
            user_id = user_data.get("user_id") or user_data.get("sub")
            if user_id:
                keys.append(f"rate:user:{user_id}")

        if mode == "login" and request.method == "POST":
            keys.append(f"rate:login_ip:{client_ip}")

        if not keys:
            keys.append(f"rate:ip:{client_ip}")


        for key in keys:
            try:
                allowed, _ = rate_limiter_script(
                    keys=[key],
                    args=[max_tokens, refill_rate, now],
                )
                if int(allowed) == 0:
                    if on_block:
                        await on_block(request, key)
                    raise HTTPException(
                        status_code=429,
                        detail="Too many requests – please try again later.",
                    )
            except redis.RedisError as exc:
                logging.error(f"Redis error in rate limiter for {key}: {exc}")
                raise HTTPException(status_code=503, detail="Rate‑limiting backend error – please try again later")


        logging.info(
            json.dumps(
                {
                    "event": "rate_limit_ok",
                    "ip": client_ip,
                    "mode": mode,
                    "keys": keys,
                    "timestamp": now,
                }
            )
        )

    return limiter
