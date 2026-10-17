import concurrent.futures
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models import WorkItem, WorkItemStatus, User


def test_07_concurrent_claims_yield_exactly_one_success(postgres_engine, db_session):
    """
    Simultaneously execute two concurrent claims on the same unassigned work item
    using two independent database sessions and HTTP clients.
    Exactly one claimant must succeed (200 OK) and the other must receive 409 Conflict.
    """
    # 1. Locate an unassigned item
    item = db_session.query(WorkItem).filter(
        WorkItem.status == WorkItemStatus.OPEN,
        WorkItem.assignee_id.is_(None)
    ).first()
    assert item is not None, "Need unassigned item for concurrent claim test"
    item_id = item.id
    target_version = item.version

    # Users in ops-core: Alice (lead) and Bob (member)
    user1_email = "lead@newtonite.io"
    user2_email = "member@newtonite.io"

    # Thread-local storage for sessions so each concurrent thread has its own isolated session
    import threading
    tls = threading.local()

    def thread_local_get_db():
        if not hasattr(tls, "session") or tls.session is None:
            conn = postgres_engine.connect()
            SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=conn)
            tls.conn = conn
            tls.session = SessionTest()
        try:
            yield tls.session
        finally:
            pass

    app.dependency_overrides[get_db] = thread_local_get_db

    def attempt_claim(user_email):
        try:
            with TestClient(app) as test_client:
                login_resp = test_client.post("/auth/login", json={"email": user_email, "password": "Password123!"})
                token = login_resp.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                resp = test_client.post(
                    f"/items/{item_id}/claim",
                    json={"version": target_version},
                    headers=headers
                )
                return resp.status_code, resp.json()
        finally:
            if hasattr(tls, "session") and tls.session:
                tls.session.close()
                tls.conn.close()
                tls.session = None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(attempt_claim, user1_email)
            f2 = executor.submit(attempt_claim, user2_email)
            res1 = f1.result()
            res2 = f2.result()
    finally:
        app.dependency_overrides.clear()

    statuses = [res1[0], res2[0]]
    assert 200 in statuses, f"Expected one successful claim, got statuses {statuses}"
    assert 409 in statuses, f"Expected one conflict response, got statuses {statuses}"

    db_session.expire_all()
    refreshed_item = db_session.query(WorkItem).filter(WorkItem.id == item_id).first()
    assert refreshed_item.assignee_id is not None
    assert refreshed_item.version == target_version + 1


def test_10_concurrent_requests_same_idempotency_key(postgres_engine, db_session):
    import threading
    lead_user = db_session.query(User).filter(User.email == "lead@newtonite.io").first()
    team_id = lead_user.team_memberships[0].team_id
    idempotency_key = "concurrent-idem-key-999"

    payload = {
        "title": "Concurrent Idempotent Incident",
        "description": "Testing racing idempotent requests",
        "type": "INCIDENT",
        "priority": "HIGH",
        "team_id": team_id
    }

    tls = threading.local()

    def thread_local_get_db():
        if not hasattr(tls, "session") or tls.session is None:
            conn = postgres_engine.connect()
            SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=conn)
            tls.conn = conn
            tls.session = SessionTest()
        try:
            yield tls.session
        finally:
            pass

    app.dependency_overrides[get_db] = thread_local_get_db

    def attempt_create():
        try:
            with TestClient(app) as test_client:
                login_resp = test_client.post("/auth/login", json={"email": "lead@newtonite.io", "password": "Password123!"})
                token = login_resp.json()["access_token"]
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": idempotency_key
                }
                resp = test_client.post("/items", json=payload, headers=headers)
                return resp.status_code, resp.json()
        finally:
            if hasattr(tls, "session") and tls.session:
                tls.session.close()
                tls.conn.close()
                tls.session = None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(attempt_create)
            f2 = executor.submit(attempt_create)
            res1 = f1.result()
            res2 = f2.result()
    finally:
        app.dependency_overrides.clear()

    assert res1[0] in (200, 201)
    assert res2[0] in (200, 201)

    db_session.expire_all()
    count = db_session.query(WorkItem).filter(WorkItem.title == "Concurrent Idempotent Incident").count()
    assert count == 1

