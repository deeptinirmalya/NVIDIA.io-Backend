"""
Team service layer - business logic for team operations.
"""
import logging
from datetime import datetime
from typing import Optional
from beanie import PydanticObjectId
from db.models.team import Team, TeamStatus
from db.models.team_member import TeamMember, TeamMemberRole, TeamMemberStatus
from db.models.event import Event
from crud.team_crud import TeamCRUD
from utils.util import generate_random_event_code

logger = logging.getLogger(__name__)


class TeamService:
    """Service layer for team operations."""

    @staticmethod
    async def create_team(
        event_id: PydanticObjectId,
        event: Event,
        team_name: str,
        captain_id: PydanticObjectId,
        session=None,
    ) -> Team:
        """
        Create a new team for a TEAM-type event.
        
        Args:
            event_id: Event ID
            event: Event model instance
            team_name: Team name
            captain_id: Captain user ID
        
        Returns:
            Created Team document
        
        Raises:
            ValueError: If event is not TEAM type or other validation fails
        """
        from db.models.event import ParticipationType
        
        if event.participation_type != ParticipationType.TEAM:
            raise ValueError("Event must be TEAM type")
        
        # Check if captain already has a team in this event
        existing_team = await TeamCRUD.get_team_by_captain(event_id, captain_id)
        if existing_team:
            raise ValueError("Captain already has a team in this event")
        
        # Generate unique team code
        team_code = generate_random_event_code(length=6)
        
        # Verify team code is unique in this event
        max_attempts = 10
        attempts = 0
        while await TeamCRUD.get_team_by_code(event_id, team_code) and attempts < max_attempts:
            team_code = generate_random_event_code(length=6)
            attempts += 1
        
        if attempts >= max_attempts:
            raise RuntimeError("Failed to generate unique team code after 10 attempts")
        
        # Create team
        team = await TeamCRUD.create_team(
            event_id=event_id,
            name=team_name,
            captain_id=captain_id,
            team_code=team_code,
            status=TeamStatus.FORMING,
            session=session,
        )
        
        # Add captain as team member
        team_member = TeamMember(
            team_id=team.id,
            event_id=event_id,
            user_id=captain_id,
            role=TeamMemberRole.CAPTAIN,
            status=TeamMemberStatus.ACTIVE,
            joined_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await team_member.insert(session=session)
        
        logger.info(f"Team created: {team.id} with code: {team_code} by captain: {captain_id}")
        return team

    @staticmethod
    async def join_team(
        event_id: PydanticObjectId,
        event: Event,
        team_code: str,
        user_id: PydanticObjectId,
    ) -> Team:
        """
        Join a team via team code.
        
        Args:
            event_id: Event ID
            event: Event model instance
            team_code: Team code (6 chars)
            user_id: User ID joining the team
        
        Returns:
            Updated Team document
        
        Raises:
            ValueError: If validation fails
        """
        from db.models.event import ParticipationType
        
        if event.participation_type != ParticipationType.TEAM:
            raise ValueError("Event must be TEAM type")
        
        # Find team by code
        team = await TeamCRUD.get_team_by_code(event_id, team_code)
        if not team:
            raise ValueError(f"Team with code {team_code} not found")
        
        # Validate team status
        if team.status not in (TeamStatus.FORMING, TeamStatus.READY):
            raise ValueError(f"Cannot join team with status: {team.status}")
        
        # Check if user already in this team
        existing_member = await TeamMember.find_one(
            {
                "team_id": team.id,
                "user_id": user_id,
            }
        )
        if existing_member:
            raise ValueError("User is already in this team")
        
        # Check if user is in another team for this event (unique constraint)
        other_team_member = await TeamMember.find_one(
            {
                "event_id": event_id,
                "user_id": user_id,
            }
        )
        if other_team_member:
            raise ValueError("User is already in another team for this event")
        
        # Check team size limits
        member_count = await TeamMember.find({"team_id": team.id}).count()
        
        if event.team_size_max and member_count >= event.team_size_max:
            raise ValueError(f"Team is full (max {event.team_size_max} members)")
        
        # Add user to team
        team_member = TeamMember(
            team_id=team.id,
            event_id=event_id,
            user_id=user_id,
            role=TeamMemberRole.MEMBER,
            status=TeamMemberStatus.ACTIVE,
            joined_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await team_member.insert()
        
        # Update team member count and check if minimum reached
        new_member_count = member_count + 1
        
        if event.team_size_min and new_member_count >= event.team_size_min and team.status == TeamStatus.FORMING:
            team = await TeamCRUD.mark_team_ready(team.id)
            logger.info(f"Team {team.id} marked as READY (min size reached)")
        
        logger.info(f"User {user_id} joined team {team.id}")
        return team

    @staticmethod
    async def get_team_members(team_id: PydanticObjectId) -> list[TeamMember]:
        """Get all active members of a team."""
        members = await TeamMember.find(
            {
                "team_id": team_id,
                "status": TeamMemberStatus.ACTIVE,
            }
        ).to_list()
        return members

    @staticmethod
    async def get_team_member_count(team_id: PydanticObjectId) -> int:
        """Get active member count for a team."""
        count = await TeamMember.find(
            {
                "team_id": team_id,
                "status": TeamMemberStatus.ACTIVE,
            }
        ).count()
        return count

    @staticmethod
    async def validate_team_for_registration(
        event_id: PydanticObjectId,
        team_id: PydanticObjectId,
        event: Event,
        captain_id: PydanticObjectId,
    ) -> bool:
        """
        Validate team before registration/payment.
        
        Args:
            event_id: Event ID
            team_id: Team ID
            event: Event model
            captain_id: Expected captain user ID
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If validation fails
        """
        team = await TeamCRUD.get_team_by_id(team_id)
        if not team:
            raise ValueError("Team not found")
        
        if team.event_id != event_id:
            raise ValueError("Team does not belong to this event")
        
        if team.captain_id != captain_id:
            raise ValueError("Only team captain can register the team")
        
        if team.status not in (TeamStatus.READY, TeamStatus.FORMING):
            raise ValueError(f"Team cannot be registered with status: {team.status}")
        
        # Verify team has minimum members
        member_count = await TeamService.get_team_member_count(team_id)
        
        if event.team_size_min and member_count < event.team_size_min:
            raise ValueError(
                f"Team must have at least {event.team_size_min} members "
                f"(currently {member_count})"
            )
        
        if event.team_size_max and member_count > event.team_size_max:
            raise ValueError(
                f"Team exceeds maximum size of {event.team_size_max} "
                f"(currently {member_count})"
            )
        
        return True

    @staticmethod
    async def remove_team_member(
        team_id: PydanticObjectId,
        user_id: PydanticObjectId,
    ) -> Optional[TeamMember]:
        """Remove a member from a team."""
        member = await TeamMember.find_one(
            {
                "team_id": team_id,
                "user_id": user_id,
            }
        )
        if member:
            member.status = TeamMemberStatus.REMOVED
            member.updated_at = datetime.utcnow()
            await member.save()
            logger.info(f"User {user_id} removed from team {team_id}")
        return member

    @staticmethod
    async def get_user_team_in_event(
        event_id: PydanticObjectId,
        user_id: PydanticObjectId,
    ) -> Optional[Team]:
        """Get team that a user belongs to in an event."""
        member = await TeamMember.find_one(
            {
                "event_id": event_id,
                "user_id": user_id,
                "status": TeamMemberStatus.ACTIVE,
            }
        )
        if member:
            team = await TeamCRUD.get_team_by_id(member.team_id)
            return team
        return None
