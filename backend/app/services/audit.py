from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models import ActivityLog, OutboxMessage, OutboxStatus


def record_activity(
    db: Session,
    work_item_id: str,
    actor_id: str,
    action: str,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    comment: Optional[str] = None
) -> ActivityLog:
    log_entry = ActivityLog(
        work_item_id=work_item_id,
        actor_id=actor_id,
        action=action,
        before_state=before_state,
        after_state=after_state,
        comment=comment
    )
    db.add(log_entry)
    return log_entry


def enqueue_outbox_message(
    db: Session,
    job_type: str,
    payload: Dict[str, Any]
) -> OutboxMessage:
    msg = OutboxMessage(
        job_type=job_type,
        payload=payload,
        status=OutboxStatus.PENDING,
        attempts=0
    )
    db.add(msg)
    return msg
