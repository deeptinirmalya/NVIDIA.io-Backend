from typing import Optional
from contextlib import asynccontextmanager
import hmac
import logging
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from api.api import api_router
from core.config import settings
from db.session import close_database, test_database_connection
from monitoring.logger import setup_logging
from monitoring.middleware import RequestLoggingMiddleware
from monitoring.sentry import init_sentry

init_sentry()
setup_logging()

ENVIRONMENT = (settings.PYTHON_ENV or "development").lower()
DEPLOYMENT_PLATFORM = settings.DEPLOYE_PLATFORM
CORS_ORIGINS = settings.BACKEND_CORS_ORIGINS

currentmode = "normal"
MAINTENANCE_ALLOWED_PATHS = [
    "/api/v1/superadmin",
    "/api/v1/superadmin",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
]

logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    connected = await test_database_connection()
    if connected:
        logger.info("Database connection successful", extra={"type": "startup_db_connection"})
    else:
        logger.error("Database connection failed", extra={"type": "startup_db_connection"})
    try:
        yield
    finally:
        await close_database()


app = FastAPI(
    title="STP API",
    version="0.1.0",
    docs_url="/docs" if ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)


@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    if currentmode.lower() == "maintenance":
        request_path = request.url.path.rstrip("/") or "/"
        allowed_path = any(
            request_path == allowed_path
            or request_path.startswith(f"{allowed_path}/")
            for allowed_path in MAINTENANCE_ALLOWED_PATHS
        )

        if not allowed_path:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "message": "Service is temporarily unavailable for maintenance.",
                    "data": None,
                    "error": "Maintenance mode",
                },
                headers={"Retry-After": "3600"},
            )

    return await call_next(request)


if DEPLOYMENT_PLATFORM == "vps":
    class VPSCloudflareMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if ENVIRONMENT == "development":
                client_ip = request.client.host if request.client else "127.0.0.1"
                user_agent = request.headers.get("user-agent", "DevClient/1.0")
            else:
                client_ip = request.headers.get("cf-connecting-ip")
                if not client_ip:
                    client_ip = request.client.host if request.client else "Unknown"
                user_agent = request.headers.get("user-agent", "Unknown")

            request.state.client_ip = client_ip
            request.state.user_agent = user_agent

            return await call_next(request)

    app.add_middleware(VPSCloudflareMiddleware)


elif DEPLOYMENT_PLATFORM == "render":
    SECRET_HEADER_NAME = settings.RENDER_SECRET_HEADER_NAME
    SECRET_HEADER_VALUE = settings.RENDER_SECRET_HEADER_VALUE

    class RenderSecurityMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if ENVIRONMENT == "development":
                client_ip = request.client.host if request.client else "127.0.0.1"
                user_agent = request.headers.get("user-agent", "DevClient/1.0")
            else:
                incoming_secret = request.headers.get(SECRET_HEADER_NAME)
                if not incoming_secret or not hmac.compare_digest(incoming_secret, SECRET_HEADER_VALUE):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Forbidden: Direct access to origin server is blocked."}
                    )

                client_ip = request.headers.get("cf-connecting-ip")
                if not client_ip:
                    client_ip = request.client.host if request.client else "Unknown"

                user_agent = request.headers.get("user-agent", "Unknown")

            request.state.client_ip = client_ip
            request.state.user_agent = user_agent

            return await call_next(request)

    app.add_middleware(RenderSecurityMiddleware)


ALLOWED_ORIGINS = set(settings.BACKEND_CORS_ORIGINS)

# Add the deployed frontend origin to ALLOWED_ORIGINS in the production environment.
def _origin_tuple(value: str):
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        port = parsed.port
    except ValueError:
        return None

    scheme = parsed.scheme.lower()
    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, parsed.hostname.lower(), port


ALLOWED_ORIGIN_TUPLES = {
    origin_tuple
    for origin in ALLOWED_ORIGINS
    if (origin_tuple := _origin_tuple(origin)) is not None
}

@app.middleware("http")
async def validate_origin_and_referer(request: Request, call_next):

    if ENVIRONMENT != "development" and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        valid_origin = _origin_tuple(origin) in ALLOWED_ORIGIN_TUPLES if origin else False
        valid_referer = _origin_tuple(referer) in ALLOWED_ORIGIN_TUPLES if referer else False

        if not (valid_origin or valid_referer):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access forbidden: Invalid or missing Origin domain."}
            )

    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
            "form-action 'none';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self' https://cdn.jsdelivr.net;"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "data": None,
            "errors": None
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):

    logger.exception(
        "Unhandled server exception",
        extra={"path": str(request.url), "method": request.method, "type": "unhandled_exception"}
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An unexpected error occurred. Please try again later.",
            "data": None,
            "error": "Internal Server Error"
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if not errors:
        error_msg = "Validation failed"
    else:
        error = errors[0]
        raw_msg: str = error.get("msg", "Validation failed")
        loc: list = error.get("loc", [])

        # Extract the field name — last element of loc, skip "body" / "query" / int indexes
        field_name = next(
            (part for part in reversed(loc) if isinstance(part, str) and part not in ("body", "query", "path")),
            None
        )

        if field_name:
            # e.g. "otp" → "Otp", "role_title" → "Role title"
            label = field_name.replace("_", " ").capitalize()
            # Replace Pydantic's generic "String should" / "Value should" with the field label
            error_msg = (
                raw_msg
                .replace("String should", f"{label} should")
                .replace("Value should", f"{label} should")
                .replace("string should", f"{label} should")
            )
        else:
            error_msg = raw_msg

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": error_msg,
            "data": None,
            "error": "Validation Error"
        }
    )

# -----------------------------------------------------------------------------
# 6. Routes
# -----------------------------------------------------------------------------
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    logger.info("application start", extra={"key_deepti": "deepti value"})
    return {"message": "Welcome to v1 API"}