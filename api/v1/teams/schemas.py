"""
Schemas for teams API.
"""
from pydantic import BaseModel, Field
from beanie import PydanticObjectId
from datetime import datetime


class CreateTeamRequest(BaseModel):
    """Request to create a new team."""
    team_name: str = Field(..., min_length=2, max_length=100, description="Team name")


class CreateTeamResponse(BaseModel):
    """Response for team creation."""
    success: bool
    message: str
    data: dict = Field(
        ...,
        example={
            "teamId": "507f1f77bcf86cd799439014",
            "teamCode": "X7K9P2",
            "teamName": "Awesome Team",
            "status": "FORMING",
            "captainId": "507f1f77bcf86cd799439011",
        }
    )


class JoinTeamRequest(BaseModel):
    """Request to join a team via code."""
    team_code: str = Field(..., min_length=6, max_length=6, description="6-character team code")


class JoinTeamResponse(BaseModel):
    """Response for joining a team."""
    success: bool
    message: str
    data: dict = Field(
        ...,
        example={
            "teamId": "507f1f77bcf86cd799439014",
            "teamCode": "X7K9P2",
            "teamName": "Awesome Team",
            "status": "FORMING",
            "memberCount": 2,
            "teamStatus": "FORMING",
        }
    )


class TeamDetailsResponse(BaseModel):
    """Response for team details."""
    team_id: str = Field(..., alias="id")
    team_code: str
    name: str
    captain_id: str
    status: str
    member_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class TeamMemberResponse(BaseModel):
    """Response for team member details."""
    user_id: str
    role: str
    status: str
    joined_at: datetime
