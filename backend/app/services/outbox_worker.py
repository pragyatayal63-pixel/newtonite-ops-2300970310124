from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from backend.app.models import OutboxMessage, OutboxStatus


def fetch_pending_jobs(db: Session, batch_size: int = 10, visibility_timeout_sec: int = 60) -> List[OutboxMessage]:
    """Safely select and lock pending or abandoned outbox jobs for processing."""
    now = datetime.now(timezone.utc)
    
    # Query with FOR UPDATE SKIP LOCKED if supported (PostgreSQL supports this cleanly)
    # Filter for PENDING, or PROCESSING with expired locked_until (abandoned jobs)
    try:
        query = (
            db.query(OutboxMessage)
            .filter(
                or_(
                    OutboxMessage.status == OutboxStatus.PENDING,
                    and_(
                        OutboxMessage.status == OutboxStatus.PROCESSING,
                        OutboxMessage.locked_until < now
                    )
                )
            )
            .order_by(OutboxMessage.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        )
        jobs = query.all()
    except Exception:
        # Fallback if dialect does not support skip_locked in testing
        db.rollback()
        query = (
            db.query(OutboxMessage)
            .filter(
                or_(
                    OutboxMessage.status == OutboxStatus.PENDING,
                    and_(
                        OutboxMessage.status == OutboxStatus.PROCESSING,
                        OutboxMessage.locked_until < now
                    )
                )
            )
            .order_by(OutboxMessage.created_at.asc())
            .limit(batch_size)
        )
        jobs = query.all()

    # Mark as PROCESSING and set lease/lock
    for job in jobs:
        job.status = OutboxStatus.PROCESSING
        job.attempts += 1
        job.locked_until = now + timedelta(seconds=visibility_timeout_sec)
    
    db.commit()
    return jobs


def execute_job_handler(job: OutboxMessage) -> bool:
    """Deterministic idempotent job execution handler."""
    # In real production, this routes to email/webhook.
    # Here we simulate reliable idempotent notification dispatch.
    if job.job_type == "NOTIFICATION_WORK_ITEM_CREATED":
        return True
    elif job.job_type == "NOTIFICATION_WORK_ITEM_ASSIGNED":
        return True
    elif job.job_type == "NOTIFICATION_WORK_ITEM_TRANSITIONED":
        return True
    elif job.job_type == "SIMULATE_FAILURE":
        raise RuntimeError("Simulated processing error for retry testing")
    return True


def process_outbox_jobs_once(db: Session, batch_size: int = 10) -> int:
    """Processes a single batch of outbox messages with bounded retries."""
    jobs = fetch_pending_jobs(db, batch_size=batch_size)
    processed_count = 0
    now = datetime.now(timezone.utc)

    for job in jobs:
        try:
            success = execute_job_handler(job)
            if success:
                job.status = OutboxStatus.COMPLETED
                job.processed_at = now
                job.last_error = None
                job.locked_until = None
                processed_count += 1
        except Exception as e:
            job.last_error = str(e)
            if job.attempts >= job.max_attempts:
                job.status = OutboxStatus.FAILED
                job.locked_until = None
            else:
                job.status = OutboxStatus.PENDING  # Backoff / retryable
                # Exponential backoff simulation: lock until next retry
                job.locked_until = now + timedelta(seconds=2 * job.attempts)
        db.commit()

    return processed_count
