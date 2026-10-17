from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, update
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_team_membership, get_authorized_item
from backend.app.core.workflow import validate_workflow_transition
from backend.app.models import (
    User,
    TeamMember,
    TeamRole,
    WorkItem,
    WorkItemType,
    WorkItemPriority,
    WorkItemStatus,
    Team
)
from backend.app.schemas import (
    WorkItemCreate,
    WorkItemUpdate,
    WorkItemTransition,
    WorkItemClaim,
    WorkItemResponse,
    WorkItemListResponse,
    ActivityResponse
)
from backend.app.services.idempotency import compute_payload_hash, check_idempotency, record_idempotency
from backend.app.services.audit import record_activity, enqueue_outbox_message

router = APIRouter(prefix="/items", tags=["items"])


def _format_item_response(item: WorkItem) -> WorkItemResponse:
    return WorkItemResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        priority=item.priority,
        status=item.status,
        team_id=item.team_id,
        team_name=item.team.name if item.team else None,
        creator_id=item.creator_id,
        creator_name=item.creator.full_name if item.creator else None,
        assignee_id=item.assignee_id,
        assignee_name=item.assignee.full_name if item.assignee else None,
        due_date=item.due_date,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@router.get("", response_model=WorkItemListResponse)
def list_work_items(
    team_id: Optional[str] = Query(None, description="Filter by team"),
    status: Optional[WorkItemStatus] = Query(None, description="Filter by status"),
    priority: Optional[WorkItemPriority] = Query(None, description="Filter by priority"),
    assignee_id: Optional[str] = Query(None, description="Filter by assignee user ID"),
    search: Optional[str] = Query(None, description="Search in title or description"),
    unassigned_urgent: Optional[bool] = Query(False, description="Filter unassigned urgent items"),
    assigned_to_me: Optional[bool] = Query(False, description="Filter items assigned to current user"),
    awaiting_my_approval: Optional[bool] = Query(False, description="Filter items awaiting my approval"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Find all teams user has access to
    my_memberships = db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
    user_team_ids = [m.team_id for m in my_memberships]
    team_roles = {m.team_id: m.role for m in my_memberships}

    if not user_team_ids:
        return WorkItemListResponse(items=[], total=0, page=page, limit=limit, has_next=False)

    # Base query restricted strictly to user's authorized teams
    query = db.query(WorkItem).filter(WorkItem.team_id.in_(user_team_ids))

    if team_id:
        if team_id not in user_team_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You are not a member of the requested team"
            )
        query = query.filter(WorkItem.team_id == team_id)

    if status:
        query = query.filter(WorkItem.status == status)

    if priority:
        query = query.filter(WorkItem.priority == priority)

    if assignee_id:
        query = query.filter(WorkItem.assignee_id == assignee_id)

    if assigned_to_me:
        query = query.filter(WorkItem.assignee_id == user.id)

    if unassigned_urgent:
        query = query.filter(
            WorkItem.assignee_id.is_(None),
            WorkItem.priority.in_([WorkItemPriority.HIGH, WorkItemPriority.CRITICAL]),
            WorkItem.status.in_([WorkItemStatus.OPEN, WorkItemStatus.IN_PROGRESS])
        )

    if awaiting_my_approval:
        # Items awaiting approval in teams where current user has LEAD or ADMIN role
        lead_team_ids = [t_id for t_id, r in team_roles.items() if r in (TeamRole.LEAD, TeamRole.ADMIN)]
        if not lead_team_ids:
            return WorkItemListResponse(items=[], total=0, page=page, limit=limit, has_next=False)
        query = query.filter(
            WorkItem.status == WorkItemStatus.AWAITING_APPROVAL,
            WorkItem.team_id.in_(lead_team_ids)
        )

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                WorkItem.title.ilike(search_filter),
                WorkItem.description.ilike(search_filter)
            )
        )

    total = query.count()
    items = (
        query.order_by(WorkItem.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    formatted_items = [_format_item_response(item) for item in items]
    has_next = (page * limit) < total

    return WorkItemListResponse(
        items=formatted_items,
        total=total,
        page=page,
        limit=limit,
        has_next=has_next
    )


@router.post("", response_model=WorkItemResponse, status_code=status.HTTP_201_CREATED)
def create_work_item(
    payload: WorkItemCreate,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Authorization: Team membership required, role must be at least MEMBER (VIEWER cannot create)
    membership = require_team_membership(
        payload.team_id,
        user,
        db,
        allowed_roles={TeamRole.MEMBER, TeamRole.LEAD, TeamRole.ADMIN}
    )

    # Validate assignee belongs to team if provided
    if payload.assignee_id:
        assignee_membership = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == payload.team_id, TeamMember.user_id == payload.assignee_id)
            .first()
        )
        if not assignee_membership:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assignee does not belong to the target team"
            )

    # Idempotency check
    payload_dict = payload.model_dump(mode="json")
    req_hash = compute_payload_hash(payload_dict)
    cached = check_idempotency(db, user.id, "CREATE_WORK_ITEM", idempotency_key, req_hash)
    if cached:
        cached_status, cached_body = cached
        response.status_code = cached_status
        return cached_body

    # Transaction: Create work item, activity log, outbox notification, idempotency record
    new_item = WorkItem(
        title=payload.title,
        description=payload.description,
        type=payload.type,
        priority=payload.priority,
        status=WorkItemStatus.OPEN,
        team_id=payload.team_id,
        creator_id=user.id,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
        version=1
    )
    db.add(new_item)
    db.flush() # Populate new_item.id

    record_activity(
        db,
        work_item_id=new_item.id,
        actor_id=user.id,
        action="CREATED",
        after_state={
            "title": new_item.title,
            "type": new_item.type.value,
            "priority": new_item.priority.value,
            "status": new_item.status.value,
            "assignee_id": new_item.assignee_id
        }
    )

    enqueue_outbox_message(
        db,
        job_type="NOTIFICATION_WORK_ITEM_CREATED",
        payload={
            "work_item_id": new_item.id,
            "title": new_item.title,
            "team_id": new_item.team_id,
            "creator_id": user.id
        }
    )

    item_response_dict = _format_item_response(new_item).model_dump(mode="json")

    record_idempotency(
        db,
        user.id,
        "CREATE_WORK_ITEM",
        idempotency_key,
        req_hash,
        status.HTTP_201_CREATED,
        item_response_dict
    )

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Check if concurrent duplicate transaction committed the idempotency key first
        if idempotency_key:
            concurrent_cached = check_idempotency(db, user.id, "CREATE_WORK_ITEM", idempotency_key, req_hash)
            if concurrent_cached:
                cached_status, cached_body = concurrent_cached
                response.status_code = cached_status
                return cached_body
        raise

    db.refresh(new_item)
    return _format_item_response(new_item)



@router.get("/{id}", response_model=WorkItemResponse)
def get_work_item(
    id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item, _ = get_authorized_item(id, user, db)
    return _format_item_response(item)


@router.patch("/{id}", response_model=WorkItemResponse)
def update_work_item(
    id: str,
    payload: WorkItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item, membership = get_authorized_item(
        id,
        user,
        db,
        allowed_roles={TeamRole.MEMBER, TeamRole.LEAD, TeamRole.ADMIN}
    )

    # Validate assignee belongs to the team
    if payload.assignee_id:
        assignee_membership = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == item.team_id, TeamMember.user_id == payload.assignee_id)
            .first()
        )
        if not assignee_membership:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assignee does not belong to this item's team"
            )

    before_state = {
        "title": item.title,
        "description": item.description,
        "priority": item.priority.value,
        "assignee_id": item.assignee_id,
        "due_date": item.due_date.isoformat() if item.due_date else None
    }

    # Optimistic locking update
    update_values = {}
    if payload.title is not None:
        update_values["title"] = payload.title
    if payload.description is not None:
        update_values["description"] = payload.description
    if payload.priority is not None:
        update_values["priority"] = payload.priority
    if payload.assignee_id is not None:
        update_values["assignee_id"] = payload.assignee_id
    if payload.due_date is not None:
        update_values["due_date"] = payload.due_date
    
    update_values["version"] = WorkItem.version + 1
    update_values["updated_at"] = datetime.now(timezone.utc)

    result = db.execute(
        update(WorkItem)
        .where(WorkItem.id == id, WorkItem.version == payload.version)
        .values(**update_values)
    )

    if result.rowcount == 0:
        db.rollback()
        # Item modified or version mismatch
        current_item = db.query(WorkItem).filter(WorkItem.id == id).first()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Conflict detected: The item was modified by another process",
                "current_version": current_item.version if current_item else None,
                "provided_version": payload.version
            }
        )

    record_activity(
        db,
        work_item_id=id,
        actor_id=user.id,
        action="UPDATED",
        before_state=before_state,
        after_state=update_values
    )

    db.commit()
    db.refresh(item)
    return _format_item_response(item)


@router.post("/{id}/claim", response_model=WorkItemResponse)
def claim_work_item(
    id: str,
    payload: WorkItemClaim,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Database-atomic claiming of an unassigned work item.
    Enforces team membership, role permissions, assignee_id is NULL,
    and optimistic locking version match.
    """
    item, membership = get_authorized_item(
        id,
        user,
        db,
        allowed_roles={TeamRole.MEMBER, TeamRole.LEAD, TeamRole.ADMIN}
    )

    # Atomic conditional update
    result = db.execute(
        update(WorkItem)
        .where(
            WorkItem.id == id,
            WorkItem.version == payload.version,
            WorkItem.assignee_id.is_(None)
        )
        .values(
            assignee_id=user.id,
            version=WorkItem.version + 1,
            updated_at=datetime.now(timezone.utc)
        )
    )

    if result.rowcount == 0:
        db.rollback()
        current_item = db.query(WorkItem).filter(WorkItem.id == id).first()
        if current_item and current_item.assignee_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Conflict detected: This item has already been claimed by another user",
                    "current_assignee_id": current_item.assignee_id,
                    "current_version": current_item.version
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Conflict detected: Work item version mismatch",
                    "current_version": current_item.version if current_item else None,
                    "provided_version": payload.version
                }
            )

    record_activity(
        db,
        work_item_id=id,
        actor_id=user.id,
        action="ASSIGNED",
        before_state={"assignee_id": None},
        after_state={"assignee_id": user.id}
    )

    enqueue_outbox_message(
        db,
        job_type="NOTIFICATION_WORK_ITEM_ASSIGNED",
        payload={
            "work_item_id": id,
            "assignee_id": user.id,
            "assigned_by": user.id
        }
    )

    db.commit()
    db.refresh(item)
    return _format_item_response(item)


@router.post("/{id}/transition", response_model=WorkItemResponse)
def transition_work_item(
    id: str,
    payload: WorkItemTransition,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item, membership = get_authorized_item(id, user, db)

    # Validate state transition & role permissions in centralized workflow service
    validate_workflow_transition(item.status, payload.status, membership.role)

    before_status = item.status.value

    # Perform atomic update with optimistic locking check
    result = db.execute(
        update(WorkItem)
        .where(
            WorkItem.id == id,
            WorkItem.version == payload.version
        )
        .values(
            status=payload.status,
            version=WorkItem.version + 1,
            updated_at=datetime.now(timezone.utc)
        )
    )

    if result.rowcount == 0:
        db.rollback()
        current_item = db.query(WorkItem).filter(WorkItem.id == id).first()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Conflict detected: Work item was modified by another operation",
                "current_version": current_item.version if current_item else None,
                "current_status": current_item.status.value if current_item else None
            }
        )

    action_label = "APPROVED" if payload.status == WorkItemStatus.RESOLVED else "STATUS_CHANGED"

    record_activity(
        db,
        work_item_id=id,
        actor_id=user.id,
        action=action_label,
        before_state={"status": before_status},
        after_state={"status": payload.status.value},
        comment=payload.comment
    )

    enqueue_outbox_message(
        db,
        job_type="NOTIFICATION_WORK_ITEM_TRANSITIONED",
        payload={
            "work_item_id": id,
            "from_status": before_status,
            "to_status": payload.status.value,
            "actor_id": user.id
        }
    )

    db.commit()
    db.refresh(item)
    return _format_item_response(item)


@router.get("/{id}/activity", response_model=List[ActivityResponse])
def get_work_item_activity(
    id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify user has access to item's team
    item, _ = get_authorized_item(id, user, db)

    activities = (
        db.query(item.__class__.activities.property.mapper.class_)
        .filter_by(work_item_id=id)
        .order_by(item.__class__.activities.property.mapper.class_.created_at.asc())
        .all()
    )

    response = []
    for act in activities:
        response.append(
            ActivityResponse(
                id=act.id,
                work_item_id=act.work_item_id,
                actor_id=act.actor_id,
                actor_name=act.actor.full_name if act.actor else None,
                action=act.action,
                before_state=act.before_state,
                after_state=act.after_state,
                comment=act.comment,
                created_at=act.created_at
            )
        )
    return response
