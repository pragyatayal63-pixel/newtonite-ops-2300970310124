from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import verify_password, create_access_token
from backend.app.core.dependencies import get_current_user
from backend.app.models import User, TeamMember, Team
from backend.app.schemas import LoginRequest, TokenResponse, UserMeResponse, TeamMembershipResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if user.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated"
        )
    
    token = create_access_token(data={"sub": user.id, "email": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserMeResponse)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = (
        db.query(TeamMember, Team)
        .join(Team, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == user.id)
        .all()
    )
    
    membership_responses = [
        TeamMembershipResponse(
            team_id=tm.team_id,
            team_name=team.name,
            team_slug=team.slug,
            role=tm.role
        )
        for tm, team in memberships
    ]
    
    return UserMeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        memberships=membership_responses
    )
