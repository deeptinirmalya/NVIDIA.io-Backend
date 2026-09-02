from datetime import datetime
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class TeamMemberRole(str, Enum):
    CAPTAIN = "CAPTAIN"
    MEMBER = "MEMBER"


class TeamMemberStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class TeamMember(Document):

    team_id: PydanticObjectId

    event_id: PydanticObjectId

    user_id: PydanticObjectId

    role: TeamMemberRole = TeamMemberRole.MEMBER

    status: TeamMemberStatus = TeamMemberStatus.ACTIVE

    joined_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    class Settings:

        name = "team_members"

        indexes = [

            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("user_id", ASCENDING)
                ],
                unique=True
            ),

            IndexModel(
                [
                    ("team_id", ASCENDING),
                    ("user_id", ASCENDING)
                ],
                unique=True
            ),

            IndexModel(
                [
                    ("team_id", ASCENDING),
                    ("status", ASCENDING)
                ]
            ),

            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("status", ASCENDING)
                ]
            ),
        ]