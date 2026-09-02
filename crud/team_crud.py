"""
Team CRUD operations for database access.
"""
from datetime import datetime
from typing import Optional
from beanie import PydanticObjectId
from db.models.team import Team, TeamStatus
from db.models.event import Event


class TeamCRUD:
    """Database operations for Team model."""

    @staticmethod
    async def create_team(
        event_id: PydanticObjectId,
        name: str,
        captain_id: PydanticObjectId,
        team_code: str,
        status: TeamStatus = TeamStatus.FORMING,
        session=None,
    ) -> Team:
        """
        Create a new team.
        
        Args:
            event_id: Event ID
            name: Team name
            captain_id: Captain user ID
            team_code: Unique team code (6 chars)
            status: Team status (default: FORMING)
        
        Returns:
            Created Team document
        """
        team = Team(
            event_id=event_id,
            name=name,
            captain_id=captain_id,
            team_code=team_code,
            status=status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await team.insert(session=session)
        return team

    @staticmethod
    async def get_team_by_id(team_id: PydanticObjectId) -> Optional[Team]:
        """Get team by ID."""
        return await Team.get(team_id)

    @staticmethod
    async def get_team_by_code(event_id: PydanticObjectId, team_code: str) -> Optional[Team]:
        """Get team by event ID and team code."""
        team = await Team.find_one(
            {
                "event_id": event_id,
                "team_code": team_code,
            }
        )
        return team

    @staticmethod
    async def get_teams_by_event(
        event_id: PydanticObjectId,
        limit: int = 100,
        skip: int = 0,
    ) -> list[Team]:
        """Get all teams for an event."""
        teams = (
            await Team.find({"event_id": event_id})
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return teams

    @staticmethod
    async def get_team_by_captain(
        event_id: PydanticObjectId,
        captain_id: PydanticObjectId,
    ) -> Optional[Team]:
        """Get team where user is captain in an event."""
        team = await Team.find_one(
            {
                "event_id": event_id,
                "captain_id": captain_id,
            }
        )
        return team

    @staticmethod
    async def count_teams(event_id: PydanticObjectId) -> int:
        """Count total teams for an event."""
        count = await Team.find({"event_id": event_id}).count()
        return count

    @staticmethod
    async def update_team_status(
        team_id: PydanticObjectId,
        status: TeamStatus,
        session=None,
    ) -> Optional[Team]:
        """Update team status."""
        team = await Team.get(team_id)
        if team:
            team.status = status
            team.updated_at = datetime.utcnow()
            await team.save(session=session)
        return team

    @staticmethod
    async def mark_team_ready(team_id: PydanticObjectId) -> Optional[Team]:
        """Mark team as READY (minimum members reached)."""
        return await TeamCRUD.update_team_status(team_id, TeamStatus.READY)

    @staticmethod
    async def mark_team_payment_pending(team_id: PydanticObjectId, session=None) -> Optional[Team]:
        """Mark team as PAYMENT_PENDING (awaiting payment)."""
        return await TeamCRUD.update_team_status(team_id, TeamStatus.PAYMENT_PENDING, session=session)

    @staticmethod
    async def confirm_team(team_id: PydanticObjectId) -> Optional[Team]:
        """Confirm team (status -> CONFIRMED)."""
        return await TeamCRUD.update_team_status(team_id, TeamStatus.CONFIRMED)

    @staticmethod
    async def cancel_team(team_id: PydanticObjectId) -> Optional[Team]:
        """Cancel team (status -> CANCELLED)."""
        return await TeamCRUD.update_team_status(team_id, TeamStatus.CANCELLED)

    @staticmethod
    async def get_teams_by_status(
        event_id: PydanticObjectId,
        status: TeamStatus,
        limit: int = 100,
    ) -> list[Team]:
        """Get teams by status."""
        teams = (
            await Team.find({"event_id": event_id, "status": status})
            .limit(limit)
            .to_list()
        )
        return teams

    @staticmethod
    async def update_team(
        team_id: PydanticObjectId,
        name: Optional[str] = None,
        status: Optional[TeamStatus] = None,
    ) -> Optional[Team]:
        """Update team details."""
        team = await Team.get(team_id)
        if team:
            if name:
                team.name = name
            if status:
                team.status = status
            team.updated_at = datetime.utcnow()
            await team.save()
        return team

    @staticmethod
    async def check_team_exists_in_event(
        event_id: PydanticObjectId,
        team_id: PydanticObjectId,
    ) -> bool:
        """Check if team belongs to an event."""
        team = await Team.find_one(
            {
                "event_id": event_id,
                "_id": team_id,
            }
        )
        return team is not None

    @staticmethod
    async def delete_team(team_id: PydanticObjectId) -> bool:
        """Delete a team (soft delete via status)."""
        team = await Team.get(team_id)
        if team:
            team.status = TeamStatus.CANCELLED
            team.updated_at = datetime.utcnow()
            await team.save()
            return True
        return False
