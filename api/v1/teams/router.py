"""
Teams API router - Team CRUD and member management.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from security.auth import token_required
from security.rate_limiter import rate_limiter
from db.models.event import Event
from services.team_service import TeamService
from crud.team_crud import TeamCRUD
from api.v1.teams.schemas import (
    CreateTeamRequest,
    CreateTeamResponse,
    JoinTeamRequest,
    JoinTeamResponse,
)

logger = logging.getLogger(__name__)

teams_router = APIRouter(prefix="/teams", tags=["Teams"])


@teams_router.post(
    "/{event_id}/create",
    response_model=CreateTeamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    event_id: str,
    request: CreateTeamRequest,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    rate_limit_dep=Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    """
    Create a new team for a TEAM-type event.
    
    Creator becomes the team captain.
    
    Returns:
    - teamId: Unique team ID
    - teamCode: 6-character code for joining (e.g., "X7K9P2")
    - teamName: Team name
    - status: Always "FORMING" for new teams
    """
    try:
        # Get event
        event = await Event.get(PydanticObjectId(event_id))
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
        
        from db.models.event import ParticipationType
        if event.participation_type != ParticipationType.TEAM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event does not support teams",
            )
        
        user_id = PydanticObjectId(user_data["user_id"])
        
        # Create team
        team = await TeamService.create_team(
            event_id=PydanticObjectId(event_id),
            event=event,
            team_name=request.team_name,
            captain_id=user_id,
        )
        
        return CreateTeamResponse(
            success=True,
            message="Team created successfully",
            data={
                "teamId": str(team.id),
                "teamCode": team.team_code,
                "teamName": team.name,
                "status": team.status,
                "captainId": str(user_id),
            },
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Team creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Team creation failed",
        )


@teams_router.post(
    "/{event_id}/join",
    response_model=JoinTeamResponse,
    status_code=status.HTTP_200_OK,
)
async def join_team(
    event_id: str,
    request: JoinTeamRequest,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    rate_limit_dep=Depends(rate_limiter(max_tokens=20, refill_rate=1.0, mode="both")),
):
    """
    Join a team via team code.
    
    Prerequisites:
    - Team code must be valid (6 characters)
    - Team must exist and belong to this event
    - User cannot already be in a team for this event
    - Team must have available slots (< max_members)
    
    Returns:
    - teamId: Team ID
    - teamCode: Team code
    - teamName: Team name
    - memberCount: Current member count
    - teamStatus: "FORMING" or "READY" (if min members reached)
    """
    try:
        # Get event
        event = await Event.get(PydanticObjectId(event_id))
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
        
        from db.models.event import ParticipationType
        if event.participation_type != ParticipationType.TEAM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event does not support teams",
            )
        
        user_id = PydanticObjectId(user_data["user_id"])
        
        # Join team
        team = await TeamService.join_team(
            event_id=PydanticObjectId(event_id),
            event=event,
            team_code=request.team_code,
            user_id=user_id,
        )
        
        # Get member count
        from services.team_service import TeamService as TS
        member_count = await TS.get_team_member_count(team.id)
        
        return JoinTeamResponse(
            success=True,
            message="Joined team successfully",
            data={
                "teamId": str(team.id),
                "teamCode": team.team_code,
                "teamName": team.name,
                "status": team.status,
                "memberCount": member_count,
                "teamStatus": team.status,
            },
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Team join error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join team",
        )


@teams_router.get(
    "/{team_id}/members",
    status_code=status.HTTP_200_OK,
)
async def get_team_members(
    team_id: str,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
):
    """
    Get all members of a team.
    """
    try:
        team = await TeamCRUD.get_team_by_id(PydanticObjectId(team_id))
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            )
        
        from services.team_service import TeamService as TS
        members = await TS.get_team_members(PydanticObjectId(team_id))
        
        return {
            "success": True,
            "data": {
                "teamId": str(team_id),
                "teamName": team.name,
                "members": [
                    {
                        "userId": str(m.user_id),
                        "role": m.role,
                        "status": m.status,
                        "joinedAt": m.joined_at.isoformat(),
                    }
                    for m in members
                ],
            },
        }
    
    except Exception as e:
        logger.error(f"Get team members error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get team members",
        )
