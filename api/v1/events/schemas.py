"""
Schemas for events API.
"""
from pydantic import BaseModel, Field
from typing import Optional
from beanie import PydanticObjectId
from decimal import Decimal


class EventDetailResponse(BaseModel):
    """Response for event details."""
    id: str = Field(..., alias="_id")
    name: str
    about: str
    category: str
    participation_type: str
    payment_type: str
    fee: Optional[Decimal]
    currency: str
    team_size_min: Optional[int]
    team_size_max: Optional[int]
    max_participants: Optional[int]
    registration_start: str
    registration_end: str
    start_time: str
    end_time: str
    status: str

    class Config:
        populate_by_name = True


class RegisterSingleFreeRequest(BaseModel):
    """Request to register for SINGLE + FREE event."""
    pass  # No additional fields needed


class RegisterSingleFreeResponse(BaseModel):
    """Response for SINGLE + FREE registration."""
    success: bool
    message: str
    data: dict = Field(
        ...,
        example={
            "registrationId": "507f1f77bcf86cd799439011",
            "status": "CONFIRMED",
            "eventId": "507f1f77bcf86cd799439012",
        }
    )


class RegisterSinglePaidRequest(BaseModel):
    """Request to initiate payment for SINGLE + PAID event."""
    pass  # No additional fields needed


class RegisterSinglePaidResponse(BaseModel):
    """Response for SINGLE + PAID registration with Razorpay order."""
    success: bool
    message: str
    data: dict = Field(
        ...,
        example={
            "razorpayOrderId": "order_IluGWxBm9U8zJ8",
            "amount": 5000,
            "currency": "INR",
            "paymentId": "507f1f77bcf86cd799439013",
            "registrationId": "507f1f77bcf86cd799439011",
        }
    )


class RegisterTeamFreeRequest(BaseModel):
    """Request to register team for TEAM + FREE event."""
    team_id: str | None = Field(default=None, description="Existing team ID")
    team_name: str | None = Field(default=None, min_length=2, max_length=100, description="Team name to create if team_id is not provided")


class RegisterTeamFreeResponse(BaseModel):
    """Response for TEAM + FREE registration."""
    success: bool
    message: str
    data: dict = Field(
        ...,
        example={
            "registrationId": "507f1f77bcf86cd799439011",
            "teamId": "507f1f77bcf86cd799439014",
            "status": "CONFIRMED",
            "memberCount": 3,
        }
    )


class RegisterTeamPaidRequest(BaseModel):
    """Request to initiate payment for TEAM + PAID event (Captain only)."""
    team_id: str | None = Field(default=None, description="Existing team ID")
    team_name: str | None = Field(default=None, min_length=2, max_length=100, description="Team name to create if team_id is not provided")


class RegisterTeamPaidResponse(BaseModel):
    """Response for TEAM + PAID registration with Razorpay order."""
    success: bool
    message: str
    data: dict = Field(
        ...,
        example={
            "razorpayOrderId": "order_IluGWxBm9U8zJ8",
            "amount": 5000,
            "currency": "INR",
            "paymentId": "507f1f77bcf86cd799439013",
            "registrationId": "507f1f77bcf86cd799439011",
            "teamId": "507f1f77bcf86cd799439014",
            "memberCount": 3,
        }
    )
