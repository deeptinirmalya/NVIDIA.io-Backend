import jwt
import os
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from sqlalchemy import select

from core.config import settings
from utils import auth_util
from db.models.auth import TokenBlacklist, User
from db.session import AsyncSessionLocal
from dependences.dependency import get_client_ip, get_user_agent
import httpx

SECRET_KEY = settings.JWT_SECRET_KEY
if settings.PYTHON_ENV == "production" and len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters in production for high-grade security")

ALGORITHM = settings.ALGORITHM

def create_access_token(user_id: int, role: str, status: str, jti: str, fingerprint: str, token_version: int):
    """Creates a short-lived access token (using config value)."""
    minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = auth_util.get_now_utc() + timedelta(minutes=minutes)
    to_encode = {
        "sub": str(user_id),
        "user_id": user_id,
        "role": role,
        "status": status,
        "jti": jti,
        "fpt": fingerprint, # Device fingerprint
        "version": token_version,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: int):
    """Creates a long-lived refresh token (7 days)."""
    expire = auth_util.get_now_utc() + timedelta(days=7)
    to_encode = {
        "sub": str(user_id),
        "user_id": user_id,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def token_required(allowed_roles: list):

    async def token_checker(request: Request):
        referer = request.headers.get("referer", "")
        is_docs_request = "/docs" in referer or "/redoc" in referer
        is_dev = settings.PYTHON_ENV == "development"

        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        
        if not token:
            token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)

        if not token:
            raise HTTPException(status_code=401, detail="Missing access token")

        if not auth_header and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            if not is_docs_request and not request.headers.get("X-Requested-With"):
                raise HTTPException(status_code=403, detail="CSRF Protection: Missing X-Requested-With header")
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")

            client = await get_client_info(request)
            current_fpt = auth_util.generate_fingerprint(client['ip'], client['user_agent'])
            token_fpt = payload.get("fpt")
            
            if token_fpt and token_fpt != current_fpt:
                raise HTTPException(status_code=401, detail="Session binding violation. Please login again.")

            jti = payload.get("jti")
            user_id = payload.get("user_id")
            token_version = payload.get("version", 1)

            # Open a short-lived SQLAlchemy session for the security checks
            async with AsyncSessionLocal() as session:
                # Check if token is blacklisted (revoked/logged out)
                stmt_blacklist = select(TokenBlacklist).where(
                    TokenBlacklist.jti == jti,
                    TokenBlacklist.expires_at > auth_util.get_now_utc()
                )
                blocked = (await session.execute(stmt_blacklist)).scalar_one_or_none()

                if blocked:
                    raise HTTPException(status_code=401, detail="Token has been revoked/logged out")

                # Fetch current user to check token version
                stmt_user = select(User).where(User.id == user_id)
                db_user = (await session.execute(stmt_user)).scalar_one_or_none()

                if db_user is None or db_user.token_version != token_version:
                    raise HTTPException(status_code=401, detail="Session revoked from all devices")

            token_status = str(payload.get("status", "")).upper()
            if token_status != "ACTIVE":
                raise HTTPException(status_code=403, detail="Account is not active")

            token_role = str(payload.get("role", "")).upper()
            if token_role not in {str(role).upper() for role in allowed_roles}:
                raise HTTPException(status_code=403, detail="Permission denied")

            request.state.user = payload
            return payload

        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
            
    return token_checker


async def get_client_info(request: Request):
    ip = get_client_ip(request)
    try:
        url = f"https://ipinfo.io/{ip}/json"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            data = response.json()

        if "country" in data:
            country = data["country"]
        else:
            country = "unknown"

        return {
            "ip": ip,
            "user_agent": get_user_agent(request),
            "country": country
        }
    except Exception as e:
        return {
            "ip": ip,
            "user_agent": get_user_agent(request),
            "country": "unknown"
        }
