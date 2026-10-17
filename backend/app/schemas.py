from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from backend.app.models import TeamRole, WorkItemType, WorkItemPriority, WorkItemStatus


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserResponse(UserBase):
    id: str
    is_active: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Auth schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Team schemas
class TeamMembershipResponse(BaseModel):
    team_id: str
    team_name: str
    team_slug: str
    role: TeamRole

    model_config = ConfigDict(from_attributes=True)


class UserMeResponse(UserResponse):
    memberships: List[TeamMembershipResponse] = []


class TeamResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    created_at: datetime
    my_role: Optional[TeamRole] = None

    model_config = ConfigDict(from_attributes=True)


class TeamMemberResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    role: TeamRole

    model_config = ConfigDict(from_attributes=True)


# Work Item schemas
class WorkItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    type: WorkItemType
    priority: WorkItemPriority
    team_id: str
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None


class WorkItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    priority: Optional[WorkItemPriority] = None
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None
    version: int = Field(..., description="Optimistic locking version")


class WorkItemTransition(BaseModel):
    status: WorkItemStatus
    version: int = Field(..., description="Optimistic locking version")
    comment: Optional[str] = None


class WorkItemClaim(BaseModel):
    version: int = Field(..., description="Optimistic locking version")


class WorkItemResponse(BaseModel):
    id: str
    title: str
    description: str
    type: WorkItemType
    priority: WorkItemPriority
    status: WorkItemStatus
    team_id: str
    team_name: Optional[str] = None
    creator_id: str
    creator_name: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    due_date: Optional[datetime] = None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkItemListResponse(BaseModel):
    items: List[WorkItemResponse]
    total: int
    page: int
    limit: int
    has_next: bool


# Activity schemas
class ActivityResponse(BaseModel):
    id: str
    work_item_id: str
    actor_id: str
    actor_name: Optional[str] = None
    action: str
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
