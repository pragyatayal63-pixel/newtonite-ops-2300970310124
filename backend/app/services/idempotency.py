import hashlib
import json
from typing import Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from backend.app.models import IdempotencyRecord


def compute_payload_hash(payload: Any) -> str:
    # Deterministic JSON serialization
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def check_idempotency(
    db: Session,
    user_id: str,
    operation: str,
    idempotency_key: Optional[str],
    payload_hash: str
) -> Optional[Tuple[int, Any]]:
    if not idempotency_key:
        return None

    record = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == idempotency_key
        )
        .first()
    )

    if not record:
        return None

    # Key exists. Verify request hash match
    if record.request_hash != payload_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key reuse detected with a different request payload"
        )

    # Return cached logical response
    return record.status_code, record.response_body


def record_idempotency(
    db: Session,
    user_id: str,
    operation: str,
    idempotency_key: Optional[str],
    payload_hash: str,
    status_code: int,
    response_body: Any
) -> None:
    if not idempotency_key:
        return

    record = IdempotencyRecord(
        user_id=user_id,
        operation=operation,
        idempotency_key=idempotency_key,
        request_hash=payload_hash,
        status_code=status_code,
        response_body=response_body
    )
    db.add(record)
