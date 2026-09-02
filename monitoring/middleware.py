import logging
import time
import uuid
import contextvars
import sentry_sdk
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from dependences.dependency import get_client_ip, get_user_agent

logger = logging.getLogger("http")

request_id_var = contextvars.ContextVar("request_id", default="")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        
        request.state.request_id = request_id
        token = request_id_var.set(request_id)

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("request_id", request_id)
            try:
                try:
                    response = await call_next(request)
                    duration_ms = round(
                        (time.perf_counter() - start_time) * 1000,
                        2,
                    )

                    logger.info(
                        f"{request.method} {request.url.path} - {response.status_code} ({duration_ms}ms)",
                        extra={
                            "event": "http_request",
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": response.status_code,
                            "duration_ms": duration_ms,
                            "client_ip": get_client_ip(request),
                            "user_agent": get_user_agent(request),
                        },
                    )

                    response.headers["X-Request-ID"] = request_id
                    return response

                except Exception:
                    duration_ms = round(
                        (time.perf_counter() - start_time) * 1000,
                        2,
                    )

                    logger.exception(
                        f"{request.method} {request.url.path} - ERROR ({duration_ms}ms)",
                        extra={
                            "event": "http_request_error",
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "duration_ms": duration_ms,
                            "client_ip": get_client_ip(request),
                            "user_agent": get_user_agent(request),
                        },
                    )
                    raise
            finally:
                request_id_var.reset(token)
