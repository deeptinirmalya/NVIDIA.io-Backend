import uuid
import httpx
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query, Header
from fastapi.responses import JSONResponse
import firebase_admin
from firebase_admin import credentials, auth
from typing import Optional
import hashlib
import secrets
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, asc

from db.models.auth import User, LoginHistory, TokenBlacklist, UserStatus, UserRole, Profile
from db.session import get_db
from security import auth as security
from security.rate_limiter import rate_limiter
from security.auth import get_client_info
from utils import auth_util, util
from templates import email_templates 


from .schemas import UserLogin, UserRegister
from core.config import settings
from monitoring.posthog import posthog

logger = logging.getLogger("auth")



# 1. Build dictionary from your existing settings instance
service_account_info = {
    "type": "service_account",
    "project_id": settings.PROJECT_ID,
    "private_key_id": settings.PRIVATE_KEY_ID,
    "private_key": settings.PRIVATE_KEY.replace("\\n", "\n") if settings.PRIVATE_KEY else "",
    "client_email": settings.CLIENT_EMAIL,
    "client_id": settings.CLIENT_ID,
    "auth_uri": settings.AUTH_URI,
    "token_uri": settings.TOKEN_URI,
    "auth_provider_x509_cert_url": settings.AUTH_PROVIDER_X509_CERT_URL,
    "client_x509_cert_url": settings.CLIENT_X509_CERT_URL,
    "universe_domain": settings.UNIVERSE_DOMAIN
}

# 2. Initialize Firebase Admin SDK once
if not firebase_admin._apps:
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)



auth_router = APIRouter()

async def verify_turnstile(request: Request, token) -> bool:

    # CLOUDFLARE_VERIFY_URL = settings.CLOUDFLARE_VERIFY_URL
    # TURNSTILE_SECRET_KEY = settings.TURNSTILE_SECRET_KEY

    # token = body.cf_turnstile_response

    # if not token:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Cloudflare Turnstile token is missing."
    #     )

    # # Retrieve the user's real IP extracted by your VPSCloudflareMiddleware
    # client_ip: Optional[str] = request.state.client_ip if hasattr(request.state, "client_ip") else None

    # # Send POST request to Cloudflare verification server
    # async with httpx.AsyncClient(timeout=5.0) as client:
    #     try:
    #         response = await client.post(
    #             CLOUDFLARE_VERIFY_URL,
    #             data={
    #                 "secret": TURNSTILE_SECRET_KEY,
    #                 "response": token,
    #                 "remoteip": client_ip, 
    #             },
    #         )
    #         result = response.json()
    #     except httpx.RequestError:
    #         raise HTTPException(
    #             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    #             detail="Unable to reach CAPTCHA verification service."
    #         )


    # if not result.get("success", False):
    #     error_codes = result.get("error-codes", [])
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail=f"CAPTCHA validation failed. Reasons: {error_codes}"
    #     )

    return True


@auth_router.get("/me")
async def get_current_user(
    user_data: dict = Depends(security.token_required(allowed_roles=["ADMIN", "STUDENT", "SUPERADMIN"]))
):
    return {
        "success": True,
        "message": "Valid session"
    }

#apply rate limit
@auth_router.post("/google")
async def google(
    request: Request,
    authorization: str = Header(..., alias="Authorization"),
    x_turnstile_token: str = Header(...),
    db: AsyncSession = Depends(get_db)
    ):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Use 'Bearer <token>'")

    token = authorization.split(" ", 1)[1].strip()

    try:
        # verify cloudeflare x_turnstile_token token
        valid_request = await verify_turnstile(request, x_turnstile_token)
        if not valid_request:
            logger.warning("Invalid request may but detected")
            raise HTTPException(status_code=403, detail="invalid request")
        
        client = await get_client_info(request)
        now = auth_util.get_now_utc()
        decoded_token = auth.verify_id_token(token, clock_skew_seconds=60)

        if not decoded_token.get("email_verified"):
            raise HTTPException(status_code=401, detail="Email not verified")

        uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        
        if not email:
            raise HTTPException(status_code=401, detail="Email not available")



        print(f"email : {email}")

        # check email patteren
        # pattern = r"^[0-9]{2}[a-zA-Z]+[0-9]{3}\.[a-zA-Z]+@giet\.edu$"
        # if not re.fullmatch(pattern, email):
        #     logger.warning(f"in valid email for registration {email}")
        #     raise HTTPException(status_code=422, detail="Email must be a valid GIET email address ")

        #check in the db
        stmt = select(User).where(User.email == email)
        user = (await db.execute(stmt)).scalar_one_or_none()

        if user:

            if not user.is_verified:
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "message": "Account not verified",
                        "data": None,
                        "error": "ACCOUNT_NOT_VEREFIED"
                    }
                )

            if user.status != UserStatus.ACTIVE:
                print("user still pending")
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "message": "Account is blocked",
                        "data": None,
                        "error": "ACCOUNT_SUSPENDED"
                    }
                )


            stmt_history = select(LoginHistory).where(LoginHistory.user_id == user.id).order_by(desc(LoginHistory.login_at)).limit(10)
            login_history = (await db.execute(stmt_history)).scalars().all()

            history_dicts = [{"ip_address": h.ip_address, "country": h.country, "user_agent": h.user_agent, "login_at": h.login_at} for h in login_history]
            
            risk = auth_util.calculate_risk(client, history_dicts)
            
            new_history = LoginHistory(
                user_id=user.id,
                ip_address=client["ip"],
                user_agent=client["user_agent"],
                country=client["country"],
                risk_score=risk,
                login_at=now
            )
            db.add(new_history)
            
            if risk >= 100:
                user.status = UserStatus.SUSPENDED
                await db.commit()  
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "message": "Risk too high. Blocked for security.",
                        "data": None,
                        "error": "HIGH_RISK_DETECTED"
                    }
                )

            user.last_login = now

            jti = str(uuid.uuid4())
            fingerprint = auth_util.generate_fingerprint(client["ip"], client["user_agent"])
            
            access_token = security.create_access_token(
                str(user.id), 
                user.role.value, 
                user.status.value, 
                jti, 
                fingerprint, 
                user.token_version
            )

            await db.flush()
            await db.commit()

            logger.info("Login DB commit successful", extra={"user_id": str(user.id)})


            response = JSONResponse(
                        status_code=200, 
                        content={
                            "success": True,
                            "message": "Logged in successfully",
                            "data": None,
                            "errors": None
                        }
                    )
            
            cookie_params = {
                "httponly": True,
                "secure": settings.COOKIE_SECURE,
                "samesite": settings.COOKIE_SAMESITE,
                "path": "/"
            }
            response.set_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, access_token, max_age=48 * 60 * 60, **cookie_params)
            
            return response

#===========================================================
        #else:

        new_user = User(
            email=email,
            google_uid=uid,
            role=UserRole.STUDENT,
            is_verified=True,
            status=UserStatus.ACTIVE,
            created_at=now
        )

        db.add(new_user)

        await db.flush()
        await db.refresh(new_user)

        # hit giet api and verify 1st then add the data to profile table for now bwlo is the demo data

        new_profile = Profile(
            user_id = new_user.id,
            roll_no="24CSEAIML189",
            contact_no="78921545567",
            name="sir ijack",
            semester=5,
            academic_session="2025-2029",
            created_at=now
        )
        db.add(new_profile)

        # send an welcome mail with instruction of app


        jti = str(uuid.uuid4())
        new_history = LoginHistory(
            user_id=new_user.id,
            ip_address=client["ip"],
            user_agent=client["user_agent"],
            country=client["country"],
            risk_score=0,
            login_at=now
        )
        db.add(new_history)

        fingerprint = auth_util.generate_fingerprint(client["ip"], client["user_agent"])

        access_token = security.create_access_token(
            str(new_user.id), 
            UserRole.STUDENT, 
            UserStatus.ACTIVE, 
            jti, 
            fingerprint, 
            new_user.token_version
        )


        await db.commit()
        logger.info("Signup db initialization is complete", extra={"email": email})

        response = JSONResponse(
                    status_code=200, 
                    content={
                        "success": True,
                        "message": "Logged in successfully",
                        "data": None,
                        "errors": None
                    }
                )
        
        cookie_params = {
            "httponly": True,
            "secure": settings.COOKIE_SECURE,
            "samesite": settings.COOKIE_SAMESITE,
            "path": "/"
        }
        response.set_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, access_token, max_age=48 * 60 * 60, **cookie_params)
        
        return response

    except HTTPException as httpe:
        await db.rollback()
        raise httpe
    except Exception as e:
        await db.rollback()
        print(f"ERROR : {str(e)}")
        logger.exception(
            "google login or sign up failed",
            extra={"error_type": type(e).__name__, "error_detail": str(e)}
        )

        raise HTTPException(status_code=500, detail=f"Internal Server Error")


# ==============================================================================================================================

@auth_router.post(
    "/admin-login", 
    dependencies=[Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="login"))]
)
async def login(
    request: Request,
    data: UserLogin, 
    client=Depends(security.get_client_info),
    session: AsyncSession = Depends(get_db)
):
    pass
    verify_user = await verify_turnstile(request, data)
    if not verify_user:
        raise HTTPException(status_code=403, detail="Bot Detected")

    stmt = select(User).where(User.email == data.identifier)
    user = (await session.execute(stmt)).scalar_one_or_none()
    
    DUMMY_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36XVyXm5WjjHyuBxmIdF4Ku"
    target_hash = user.password_hash if user else DUMMY_HASH
    password_is_correct = auth_util.verify_password(data.password, target_hash)
    
    if not user or not password_is_correct:
        print(f"invalid details {data.identifier} || {data.password}")
        posthog.capture(distinct_id=data.identifier, event="user_login_failed", properties={"reason": "invalid_credentials"})
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Invalid credentials",
                "data": None,
                "error": "INVALID_CREDENTIALS"
            }
        )
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=409, detail="Unauthorize")

    if user.status == UserStatus.INACTIVE:
        print("user still pending")
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Account not verified",
                "data": None,
                "error": "ACCOUNT_NOT_VERIFIED"
            }
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=403,
            detail="Account is blocked"
        )

    if not user.is_verified:
        raise HTTPException(status_code=401, detail="Account is not verified"
        )

    stmt_history = select(LoginHistory).where(LoginHistory.user_id == user.id).order_by(desc(LoginHistory.login_at)).limit(10)
    login_history = (await session.execute(stmt_history)).scalars().all()

    history_dicts = [{"ip_address": h.ip_address, "country": h.country, "user_agent": h.user_agent, "login_at": h.login_at} for h in login_history]
    
    risk = auth_util.calculate_risk(client, history_dicts)
    
    try:
        now = auth_util.get_now_utc()

        new_history = LoginHistory(
            user_id=user.id,
            ip_address=client["ip"],
            user_agent=client["user_agent"],
            country=client["country"],
            risk_score=risk,
            login_at=now
        )
        session.add(new_history)
        
        if risk >= 100:
            await session.commit()  
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": "Risk too high. Blocked for security.",
                    "data": None,
                    "error": "HIGH_RISK_DETECTED"
                }
            )

        user.last_login = now

        jti = str(uuid.uuid4())
        fingerprint = auth_util.generate_fingerprint(client["ip"], client["user_agent"])
        
        access_token = security.create_access_token(
            str(user.id), 
            user.role.value, 
            user.status.value, 
            jti, 
            fingerprint, 
            user.token_version
        )

        # commit all login DB writes
        await session.commit()
        logger.info("Login DB commit successful", extra={"user_id": str(user.id)})

    except Exception as e:
        await session.rollback()
        logger.exception("Database error during login", exc_info=e)
        raise HTTPException(status_code=500, detail="Database error during login")

    posthog.capture(distinct_id=data.identifier, event="user_logged_in", properties={"role": user.role.value})

    response = JSONResponse(
        status_code=200, 
        content={
            "success": True,
            "message": "Logged in successfully",
            "data": {"role": user.role.value},
            "errors": None
        }
    )
    
    cookie_params = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": "/"
    }

    response.set_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, access_token, max_age= 8 * 60 * 60, **cookie_params)
    
    return response


@auth_router.post("/super-admin-login")
async def super_admin_login():
    pass



# ==============================================================================================================================



@auth_router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    super_logout: bool = False,
    user_data: dict = Depends(security.token_required(allowed_roles=[r.value for r in UserRole])),
    session: AsyncSession = Depends(get_db)
):
    try:
        # stp 1: Blacklist the current Access Token JTI
        new_blacklist = TokenBlacklist(
            jti=user_data.get("jti"),
            expires_at=auth_util.get_now_utc() + timedelta(minutes=15)
        )
        session.add(new_blacklist)

        user_id = int(user_data.get("user_id"))
        posthog.capture(distinct_id=str(user_id), event="user_logged_out", properties={"super_logout": super_logout})

        if super_logout:
            # Increment token_version to invalidate all existing access tokens across all devices
            stmt_user = select(User).where(User.id == user_id)
            user = (await session.execute(stmt_user)).scalar_one_or_none()
            if user:
                user.token_version += 1

        await session.flush()
        await session.commit()
        logger.info("Logout DB commit successful", extra={"user_id": str(user_id), "super_logout": super_logout})

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Database error during logout", exc_info=e)
        raise HTTPException(status_code=500, detail="Database error during logout")

    # Clear Cookies
    response_obj = JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Logged out from all devices successfully" if super_logout else "Logged out successfully",
            "data": None,
            "errors": None
        }
    )
    response_obj.delete_cookie(settings.ACCESS_TOKEN_COOKIE_NAME,path="/",secure=settings.COOKIE_SECURE,samesite=settings.COOKIE_SAMESITE)

    return response_obj


# @auth_router.get("/sessions")
# async def list_sessions(
#     user_data: dict = Depends(security.token_required(allowed_roles=[r.value for r in UserRole])),
#     session: AsyncSession = Depends(get_db)
# ):
#     """List active sessions (refresh tokens) for the current user."""
#     user_id = int(user_data.get("user_id"))
#     stmt = select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
#     sessions = (await session.execute(stmt)).scalars().all()
    
#     return {
#         "success": True,
#         "message": "Active sessions retrieved",
#         "data": [{"id": str(s.id), "ip_address": s.ip_address, "user_agent": s.user_agent, "expires_at": s.expires_at.isoformat()} for s in sessions]
#     }
