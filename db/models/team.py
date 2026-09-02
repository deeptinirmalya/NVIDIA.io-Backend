from datetime import datetime
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class TeamStatus(str, Enum):
    FORMING = "FORMING"
    READY = "READY"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class Team(Document):

    event_id: PydanticObjectId

    name: str = Field(
        min_length=2,
        max_length=100
    )

    captain_id: PydanticObjectId

    team_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Unique team code for joining via code (e.g., X7K9P2)"
    )

    status: TeamStatus = TeamStatus.FORMING

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    class Settings:

        name = "teams"

        indexes = [
            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("name", ASCENDING)
                ],
                unique=True
            ),

            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("team_code", ASCENDING)
                ],
                unique=True,
                name="event_team_code_unique"
            ),

            IndexModel(
                [
                    ("event_id", ASCENDING),
                    ("captain_id", ASCENDING)
                ]
            ),

            IndexModel(
                [("created_at", DESCENDING)]
            ),
        ]