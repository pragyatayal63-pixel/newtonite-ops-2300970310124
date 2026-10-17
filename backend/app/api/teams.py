from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_team_membership
from backend.app.models import User, Team, TeamMember
from backend.app.schemas import TeamResponse, TeamMemberResponse

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=List[TeamResponse])
def list_my_teams(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List teams that the current authenticated user belongs to."""
    results = (
        db.query(Team, TeamMember.role)
        .join(TeamMember, Team.id == TeamMember.team_id)
        .filter(TeamMember.user_id == user.id)
        .all()
    )
    
    response = []
    for team, role in results:
        t_dict = {
            "id": team.id,
            "name": team.name,
            "slug": team.slug,
            "description": team.description,
            "created_at": team.created_at,
            "my_role": role
        }
        response.append(TeamResponse(**t_dict))
    return response


@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
def get_team_members(
    team_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List members of a team, accessible only to members of that team."""
    require_team_membership(team_id, user, db)

    members = (
        db.query(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .filter(TeamMember.team_id == team_id)
        .all()
    )

    return [
        TeamMemberResponse(
            user_id=u.id,
            full_name=u.full_name,
            email=u.email,
            role=tm.role
        )
        for tm, u in members
    ]
