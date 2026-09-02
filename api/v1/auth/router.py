import base64
import uuid
import httpx
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Query
from fastapi.responses import JSONResponse
from typing import Optional
import hashlib
import secrets

from bson import ObjectId
from db.models.auth import User, EmailVerification, RefreshToken, LoginHistory, TokenBlacklist, UserStatus, UserRole, EmailVerificationStatus
from db.session import get_tx_session
from security import auth as security
from security.rate_limiter import rate_limiter
from utils import auth_util, util
from templates import email_templates 


from .schemas import UserLogin, UserRegister, ResendVerification
from core.config import settings
from monitoring.posthog import posthog

logger = logging.getLogger("auth")


auth_router = APIRouter()

async def verify_turnstile(request: Request, body: UserLogin) -> bool:

    # CLOUDFLARE_VERIFY_URL = settings.CLOUDFLARE_VERIFY_URL
    # TURNSTILE_SECRET_KEY = settings.TURNSTILE_SECRET_KEY

    # token = body.cf_turnstile_response

    # if not token:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Cloudflare Turnstile token is missing."
    #     )

    # # Retrieve the user's real IP extracted by your VPSCloudflareMiddleware
    # client_ip: Optional[str] = getattr(request.state, "client_ip", None)

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

@auth_router.get("/profile")
async def get_profile(
    user_data: dict = Depends(security.token_required(allowed_roles=["ADMIN", "STUDENT", "SUPERADMIN"]))
):
    user_id = user_data.get("user_id")
    user = await User.get(ObjectId(user_id) if isinstance(user_id, str) and len(user_id) == 24 else user_id)

    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {
        "success": True,
        "message": "Profile retrieved",
        "data": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "status": user.status.value if hasattr(user.status, 'value') else user.status,
            "created_at": user.created_at.isoformat()
        }
    }


@auth_router.post("/register")
async def register_user(
    data: UserRegister,
    session=Depends(get_tx_session),
    _=Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="login"))
):
    logger.info("Received user registration request", extra={"email": data.email, "user_name": data.name})
    
    # stp 1: Check existing user
    existing_user_docs = await User.find_one(User.email == data.email)
    if existing_user_docs:
        logger.warning("Registration failed: Email already registered", extra={"email": data.email})
        posthog.capture(distinct_id=data.email, event="user_registration_failed", properties={"reason": "email_already_exists"})
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # stp 2: Validate password (do this BEFORE database insertions)
    st, msg = auth_util.validate_password(data.password)
    if not st:
        logger.warning("Registration failed: Password validation failed", extra={"email": data.email, "reason": msg})
        raise HTTPException(status_code=422, detail=msg)

    try:
        now = auth_util.get_now_utc()

        # stp 3: Insert user 
        new_user = User(
            name=data.name,
            email=data.email,
            password_hash=auth_util.hash_password(data.password),
            created_at=now
        )
        await new_user.insert(session=session)
        logger.info("Successfully inserted user record", extra={"user_id": str(new_user.id), "email": data.email})

        # stp 4: Create verification token
        plain_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()

        # stp 5: Save token linked to User document
        new_verification_token = EmailVerification(
            user_id=new_user,
            token_hash=hashed_token,
            expires_at=now + timedelta(minutes=15),
            created_at=now
        )
        await new_verification_token.insert(session=session)

        # stp 6: Dispatch verification email (outside transaction)
        try:
            link = f"{settings.BACKEND_URL}/api/v1/auth/verify-email?token={plain_token}"
            subject, body = email_templates.verify_email(data.email, link)
            util.mail_service(subject, body, data.email, 9)
            logger.info("Verification email sent", extra={"email": data.email})
            posthog.capture(distinct_id=data.email, event="user_registered", properties={"email": data.email})
        except Exception as mail_err:
            logger.exception("Failed to send verification email", extra={"email": data.email})

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Account created. Please verify your email.",
                "data": None,
                "error": None
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create user", exc_info=exc)
        raise HTTPException(status_code=500, detail="Could not create user")


@auth_router.get("/verify-email")
async def verify_mail(
    token: str,
    session=Depends(get_tx_session),
    _= Depends(rate_limiter(max_tokens=30, refill_rate=1, mode="ip"))
):
    try:
            # stp 1: Hash the token
            hashed_token = hashlib.sha256(token.encode()).hexdigest()
            now = auth_util.get_now_utc()

            # stp 2: Find active verification token
            verification = await EmailVerification.find_one(
                EmailVerification.token_hash == hashed_token,
                EmailVerification.status == EmailVerificationStatus.ACTIVE,
                session=session,
            )

            if not verification:
                logger.warning("Invalid or already used verification token")
                raise HTTPException(status_code=400, detail="Invalid or expired verification link")

            # Step 3: Check token expiration
            if now > util.ensure_aware(verification.expires_at):
                await verification.set(
                    {
                        EmailVerification.status: EmailVerificationStatus.EXPIRED,
                    },
                    session=session,
                )

                logger.warning("Verification token expired")
                raise HTTPException(status_code=400, detail="Invalid or expired verification link")

            # stp 4: Mark verification token as USED
            await verification.set(
                {
                    EmailVerification.status: EmailVerificationStatus.USED,
                    EmailVerification.used_at: now,
                },
                session=session,
            )

            # stp 5: Verify user
            user = await User.find_one(
                User.id == verification.user_id.ref.id,
                session=session,
            )

            if not user:
                logger.error("User associated with verification token not found",extra={"user_id": str(verification.user_id.ref.id)})
                raise HTTPException(status_code=500, detail="Associated user not found")

            await user.set(
                {
                    User.is_verify: True,
                    User.updated_at: now,
                    User.status: UserStatus.ACTIVE
                },
                session=session,
            )

            # stp 6: Success
            logger.info("User email verified",extra={"user_id": str(user.id)})

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Account verified successfully",
                    "data": None,
                    "error": None,
                },
            )

    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.exception("Error during email verification", extra={"error": str(e)})
        raise HTTPException(status_code=500,detail="Internal Server Error")


@auth_router.post("/resend-verification")
async def resend_verification(
    data: ResendVerification,
    session=Depends(get_tx_session),
    _=Depends(rate_limiter(max_tokens=3, refill_rate=0.05, mode="login"))
):
    try:
        # stp 1: Find user by email
        user = await User.find_one(User.email == data.email)

        # stp 2: Validate user existence and verification status
        if not user:
            logger.warning("Resend verification failed: Email not registered", extra={"email": data.email})
            raise HTTPException(status_code=404, detail="Email not registered")

        if user.is_verify:
            logger.warning("Resend verification failed: Email already verified", extra={"email": data.email})
            raise HTTPException(status_code=400, detail="Email already verified")

        now = auth_util.get_now_utc()

        # stp 3: expire any active verification tokens
        active_verifications = await EmailVerification.find(
            EmailVerification.user_id.id == user.id,
            EmailVerification.status == EmailVerificationStatus.ACTIVE,
            session=session
        ).to_list()
        for verification in active_verifications:
            await verification.set({EmailVerification.status: EmailVerificationStatus.EXPIRED}, session=session)

        # stp 3: generate new verification token
        plain_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(plain_token.encode()).hexdigest()

        new_verification_token = EmailVerification(
            user_id=user,
            token_hash=hashed_token,
            expires_at=now + timedelta(minutes=15),
            created_at=now
        )
        await new_verification_token.insert(session=session)

        # stp 5: dispatch new email varification
        try:
            link = f"{settings.FRONTEND_URL}/api/v1/auth/verify-email?token={plain_token}"
            subject, body = email_templates.verify_email(user.email, link)
            util.mail_service(subject, body, user.email, 9)
            logger.info("Resent verification email sent", extra={"email": user.email})
        except Exception as mail_err:
            logger.exception("Failed to resend verification email", extra={"email": user.email})

        # stp 6: success response
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Verification link has been sent to your email",
                "data": None,
                "error": None
            }
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to resend verification link", exc_info=exc)
        raise HTTPException(status_code=500, detail="Could not resend verification link")




@auth_router.post(
    "/login", 
    dependencies=[Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="login"))]
)
async def login(
    request: Request,
    data: UserLogin, 
    client=Depends(security.get_client_info)
):

    verify_user = await verify_turnstile(request, data)
    if not verify_user:
        raise HTTPException(status_code=403, detail="Bot Detected")

    user = await User.find_one(User.email == data.identifier)
    

    DUMMY_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36XVyXm5WjjHyuBxmIdF4Ku"
    target_hash = user.password_hash if user else DUMMY_HASH
    password_is_correct = auth_util.verify_password(data.password, target_hash)
    

    if not user or not password_is_correct:
        print(f"uinvalid details {data.identifier} || {data.password}")
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

    if user.status == UserStatus.PENDING:
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

    if not user.is_verify:
        raise HTTPException(
            status_code=401,
            detail="Account is not verified"
        )


    login_history = await LoginHistory.find(LoginHistory.user_id == user.id).sort(-LoginHistory.login_at).limit(10).to_list()

    history_dicts = [{"ip_address": h.ip_address, "country": h.country, "user_agent": h.user_agent, "login_at": h.login_at} for h in login_history]
    
    risk = auth_util.calculate_risk(client, history_dicts)
    
    try:

        new_history = LoginHistory(
            user_id=user.id,
            ip_address=client["ip"],
            user_agent=client["user_agent"],
            country=client["country"],
            risk_score=risk
        )
        await new_history.insert()
        

        if risk >= 100:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": "Risk too high. Blocked for security.",
                    "data": None,
                    "error": "HIGH_RISK_DETECTED"
                }
            )


        user.last_login = auth_util.get_now_utc()
        await user.save()


        jti = str(uuid.uuid4())
        fingerprint = auth_util.generate_fingerprint(client["ip"], client["user_agent"])
        
        access_token = security.create_access_token(
            str(user.id), user.role.value if hasattr(user.role, 'value') else user.role, user.status.value if hasattr(user.status, 'value') else user.status, jti, fingerprint, user.token_version
        )
        refresh_token = security.create_refresh_token(str(user.id))


        new_refresh = RefreshToken(
            user_id=user.id,
            token_hash=auth_util.hash_password(refresh_token),
            expires_at=auth_util.get_now_utc() + timedelta(days=7),
            ip_address=client["ip"],
            user_agent=client["user_agent"]
        )
        await new_refresh.insert()

    except Exception as e:

        raise HTTPException(status_code=500, detail="Database error during login")

    posthog.capture(distinct_id=data.identifier, event="user_logged_in", properties={"role": user.role.value if hasattr(user.role, 'value') else user.role})

    response = JSONResponse(
        status_code=200, 
        content={
            "success": True,
            "message": "Logged in successfully",
            "data": {"role": user.role.value if hasattr(user.role, 'value') else user.role},
            "errors": None
        }
    )
    
    cookie_params = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": "/"
    }

    response.set_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, refresh_token, max_age=7 * 24 * 3600, **cookie_params)
    response.set_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, access_token, max_age=15 * 60, **cookie_params)
    
    return response


@auth_router.post(
    "/refresh",
    dependencies=[Depends(rate_limiter(max_tokens=10, refill_rate=1.0, mode="ip"))]
)
async def refresh_token(request: Request, response: Response):

    refresh_token_cookie = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token_cookie:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    try:
        payload = security.jwt.decode(
            refresh_token_cookie, 
            security.SECRET_KEY, 
            algorithms=[security.ALGORITHM]
        )
        user_id = str(payload.get("user_id"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh session")

    all_tokens = await RefreshToken.find(RefreshToken.user_id == ObjectId(user_id)).to_list()
    
    matching_token = next((t for t in all_tokens if auth_util.verify_password(refresh_token_cookie, t.token_hash)), None)
            
    if not matching_token:
        raise HTTPException(status_code=401, detail="Session not found")

    if matching_token.revoked:
        await RefreshToken.find(RefreshToken.user_id == ObjectId(user_id)).update({"$set": {"revoked": True}})
        raise HTTPException(status_code=403, detail="Security breach detected. All sessions revoked.")


    user_history = await LoginHistory.find(LoginHistory.user_id == ObjectId(user_id)).sort(+LoginHistory.login_at).to_list()
    history_dicts = [{"ip_address": h.ip_address, "country": h.country, "user_agent": h.user_agent, "login_at": h.login_at} for h in user_history]


    client = await security.get_client_info(request)
    risk = auth_util.calculate_risk_refresh(client, history_dicts) 
    
    if risk >= 100:
        await RefreshToken.find(RefreshToken.user_id == ObjectId(user_id)).update({"$set": {"revoked": True}})
        raise HTTPException(status_code=403, detail="Risk anomaly detected. Please log in again.")


    user = await User.get(ObjectId(user_id) if isinstance(user_id, str) and len(user_id) == 24 else user_id)
    
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account restricted")

    matching_token.revoked = True
    await matching_token.save()
    
    new_jti = str(uuid.uuid4())
    fingerprint = auth_util.generate_fingerprint(client["ip"], client["user_agent"])
    
    new_access_token = security.create_access_token(
        str(user.id), user.role.value if hasattr(user.role, 'value') else user.role, user.status.value if hasattr(user.status, 'value') else user.status, new_jti, fingerprint, user.token_version
    )
    new_refresh_token = security.create_refresh_token(str(user.id))
    

    await RefreshToken(
        user_id=user.id,
        token_hash=auth_util.hash_password(new_refresh_token),
        expires_at=auth_util.get_now_utc() + timedelta(days=7),
        ip_address=client["ip"],
        user_agent=client["user_agent"]
    ).insert()
    
    await LoginHistory(
        user_id=user.id,
        ip_address=client["ip"],
        user_agent=client["user_agent"],
        country=client.get("country"),
        risk_score=risk
    ).insert()


    response_obj = JSONResponse(content={"success": True, "message": "Session rotated"})
    
    cookie_settings = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": "/"
    }

    response_obj.set_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, new_refresh_token, max_age=7*24*3600, **cookie_settings)
    response_obj.set_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, new_access_token, max_age=900, **cookie_settings)
    
    return response_obj


@auth_router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    super_logout: bool = False,
    user_data: dict = Depends(security.token_required(allowed_roles=[r.value for r in UserRole]))
):
    # 1. Blacklist the current Access Token JTI
    new_blacklist = TokenBlacklist(
        jti=user_data.get("jti"),
        expires_at=auth_util.get_now_utc() + timedelta(minutes=15)
    )
    await new_blacklist.insert()

    user_id_str = str(user_data.get("user_id"))
    posthog.capture(distinct_id=user_id_str, event="user_logged_out", properties={"super_logout": super_logout})

    if super_logout:
        # Revoke all refresh tokens for this user
        await RefreshToken.find(RefreshToken.user_id == user_id_str).update({"$set": {"revoked": True}})
        
        # Increment token_version to invalidate all existing access tokens across all devices
        user = await User.get(ObjectId(user_id_str) if isinstance(user_id_str, str) and len(user_id_str) == 24 else user_id_str)
        if user:
            user.token_version += 1
            await user.save()
    else:
        # Revoke the current refresh token from the cookie
        refresh_token_cookie = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
        if refresh_token_cookie:
            # We must find the refresh token that matches the hash
            all_tokens = await RefreshToken.find(
                RefreshToken.user_id == user_id_str,
                RefreshToken.revoked == False
            ).to_list()
            
            matching_token = next((t for t in all_tokens if auth_util.verify_password(refresh_token_cookie, t.token_hash)), None)
            if matching_token:
                matching_token.revoked = True
                await matching_token.save()

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
    response_obj.delete_cookie(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )
    response_obj.delete_cookie(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )

    return response_obj


@auth_router.get("/sessions")
async def list_sessions(
    user_data: dict = Depends(security.token_required(allowed_roles=[r.value for r in UserRole]))
):
    """List active sessions (refresh tokens) for the current user."""
    user_id_str = str(user_data.get("user_id"))
    sessions = await RefreshToken.find(
        RefreshToken.user_id == user_id_str,
        RefreshToken.revoked == False
    ).to_list()
    
    return {
        "success": True,
        "message": "Active sessions retrieved",
        "data": [{"id": str(s.id), "ip_address": s.ip_address, "user_agent": s.user_agent, "expires_at": s.expires_at.isoformat()} for s in sessions]
    }

@auth_router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    user_data: dict = Depends(security.token_required(allowed_roles=[r.value for r in UserRole]))
):
    """Revoke a specific session."""
    try:
        session = await RefreshToken.get(ObjectId(session_id) if isinstance(session_id, str) and len(session_id) == 24 else session_id)
        if not session or session.user_id != str(user_data.get("user_id")):
            raise HTTPException(status_code=404, detail="Session not found")

        session.revoked = True
        await session.save()
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "message": f"Session {session_id} revoked successfully"
    }
