import enum
from datetime import datetime
from typing import Optional, List, Annotated
from beanie import Document, Indexed, Link, PydanticObjectId
from pydantic import Field, EmailStr
from bson import ObjectId
from pydantic import ConfigDict
from utils import auth_util
from decimal import Decimal
from enum import Enum
from pydantic import Field, field_validator
from pymongo import IndexModel, ASCENDING, DESCENDING


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"
    STUDENT = "STUDENT"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"
    SUSPENDED = "SUSPENDED"

class EmailVerificationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"




class User(Document):
    email: Annotated[str, Indexed(unique=True)]
    name: str
    password_hash: str
    
    role: UserRole = UserRole.STUDENT
    
    status: UserStatus = UserStatus.PENDING
    is_verify: bool = False
    token_version: int = 1
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=auth_util.get_now_utc)
    updated_at: Optional[datetime] = None
    is_deleted: bool = False

    class Settings:
        name = "users"

class EmailVerification(Document):
    user_id: Link[User]
    token_hash: Annotated[str, Indexed(unique=True)]
    expires_at: datetime
    status: EmailVerificationStatus = EmailVerificationStatus.ACTIVE
    created_at: datetime
    used_at: Optional[datetime] = None

    class Settings:
        name = "email_verification"


class RefreshToken(Document):
    user_id: PydanticObjectId
    token_hash: str
    expires_at: datetime
    revoked: bool = False
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    class Settings:
        name = "refresh_tokens"


class LoginHistory(Document):
    user_id: PydanticObjectId
    ip_address: str
    user_agent: str
    country: Optional[str] = None
    risk_score: int = 0
    login_at: datetime = Field(default_factory=auth_util.get_now_utc)

    class Settings:
        name = "login_history"


class TokenBlacklist(Document):
    jti: Annotated[str, Indexed(unique=True)]
    expires_at: datetime

    class Settings:
        name = "token_blacklist"




#