from typing import Dict, Set, Tuple
from fastapi import HTTPException, status
from backend.app.models import WorkItemStatus, TeamRole

# Workflow Transition Map:
# Current Status -> Set of (Next Status, Set of Allowed TeamRoles)
ALLOWED_TRANSITIONS: Dict[WorkItemStatus, Dict[WorkItemStatus, Set[TeamRole]]] = {
    WorkItemStatus.OPEN: {
        WorkItemStatus.IN_PROGRESS: {TeamRole.MEMBER, TeamRole.LEAD, TeamRole.ADMIN},
    },
    WorkItemStatus.IN_PROGRESS: {
        WorkItemStatus.AWAITING_APPROVAL: {TeamRole.MEMBER, TeamRole.LEAD, TeamRole.ADMIN},
        WorkItemStatus.OPEN: {TeamRole.MEMBER, TeamRole.LEAD, TeamRole.ADMIN}, # Un-start back to OPEN
    },
    WorkItemStatus.AWAITING_APPROVAL: {
        WorkItemStatus.RESOLVED: {TeamRole.LEAD, TeamRole.ADMIN}, # LEAD approval required!
        WorkItemStatus.IN_PROGRESS: {TeamRole.LEAD, TeamRole.ADMIN}, # Reject back to IN_PROGRESS by Lead
    },
    WorkItemStatus.RESOLVED: {
        WorkItemStatus.CLOSED: {TeamRole.MEMBER, TeamRole.LEAD, TeamRole.ADMIN},
    },
    WorkItemStatus.CLOSED: {} # Terminal state; no transitions permitted out of CLOSED
}


def validate_workflow_transition(
    current_status: WorkItemStatus,
    target_status: WorkItemStatus,
    user_role: TeamRole
) -> None:
    if current_status == target_status:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Work item is already in status {current_status.value}"
        )
    
    valid_targets = ALLOWED_TRANSITIONS.get(current_status, {})
    if target_status not in valid_targets:
        allowed_list = [s.value for s in valid_targets.keys()]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid transition from {current_status.value} to {target_status.value}. Allowed transitions from {current_status.value}: {allowed_list}"
        )
    
    permitted_roles = valid_targets[target_status]
    if user_role not in permitted_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Transitioning from {current_status.value} to {target_status.value} requires one of {[r.value for r in permitted_roles]}, but you are {user_role.value}"
        )
