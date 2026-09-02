from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class UserRegister(BaseModel):
    name: str = Field(...,min_length=5, max_length=200, description="The user's name")
    email: EmailStr = Field(..., description="The user's email address")
    password: str = Field(..., min_length=8, description="The user's plain-text password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        pattern = r"^[a-z0-9]+(?:\.[a-z0-9]+)*@giet\.edu$"

        if not re.fullmatch(pattern, value):
            raise ValueError(
                "Email must be a valid GIET email address "
                "and only numbers, and '.' are allowed"
            )

        return value


class UserLogin(BaseModel):
    identifier: EmailStr = Field(..., description="The user's email address ")
    password: str = Field(..., min_length=8, description="The user's plain-text password")
    cf_turnstile_response: str = Field(...)


class ResendVerification(BaseModel):
    email: EmailStr = Field(..., description="The user's email address")




