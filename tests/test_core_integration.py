import pytest
from backend.app.models import WorkItem, WorkItemStatus, OutboxMessage, OutboxStatus
from backend.app.services.outbox_worker import process_outbox_jobs_once


def test_01_login_and_unauthenticated_rejection(client):
    # 1. Unauthenticated rejection
    resp = client.get("/auth/me")
    assert resp.status_code == 401

    # 2. Invalid credentials
    resp = client.post("/auth/login", json={"email": "lead@newtonite.io", "password": "WrongPassword!"})
    assert resp.status_code == 401

    # 3. Successful login
    resp = client.post("/auth/login", json={"email": "lead@newtonite.io", "password": "Password123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "lead@newtonite.io"


def test_02_viewer_cannot_perform_write_operations(client, auth_headers, db_session):
    headers = auth_headers("viewer@newtonite.io")

    # Viewer can read me and teams
    resp = client.get("/teams", headers=headers)
    assert resp.status_code == 200
    ops_team_id = resp.json()[0]["id"]

    # Viewer cannot create work item
    create_payload = {
        "title": "Unauthorized Item",
        "description": "Should fail",
        "type": "TASK",
        "priority": "LOW",
        "team_id": ops_team_id
    }
    resp = client.post("/items", json=create_payload, headers=headers)
    assert resp.status_code == 403

    # Viewer cannot claim items
    open_item = db_session.query(WorkItem).filter(WorkItem.status == WorkItemStatus.OPEN, WorkItem.assignee_id.is_(None)).first()
    resp = client.post(f"/items/{open_item.id}/claim", json={"version": open_item.version}, headers=headers)
    assert resp.status_code == 403


def test_03_member_cannot_perform_lead_only_approval(client, auth_headers, db_session):
    member_headers = auth_headers("member@newtonite.io")

    # Locate awaiting approval item
    item = db_session.query(WorkItem).filter(WorkItem.status == WorkItemStatus.AWAITING_APPROVAL).first()
    assert item is not None

    # Member attempts to approve to RESOLVED
    resp = client.post(
        f"/items/{item.id}/transition",
        json={"status": "RESOLVED", "version": item.version, "comment": "Trying to approve as member"},
        headers=member_headers
    )
    assert resp.status_code == 403
    assert "requires one of" in resp.json()["detail"]


def test_04_cross_team_reads_and_writes_are_rejected(client, auth_headers, db_session):
    # Diana is Lead for fin-compliance, but not Ops Core
    diana_headers = auth_headers("finlead@newtonite.io")

    # Item belonging to Ops Core
    ops_item = db_session.query(WorkItem).join(WorkItem.team).filter(WorkItem.team.has(slug="ops-core")).first()

    # Cross-team read
    resp = client.get(f"/items/{ops_item.id}", headers=diana_headers)
    assert resp.status_code == 403

    # Cross-team transition
    resp = client.post(
        f"/items/{ops_item.id}/transition",
        json={"status": "IN_PROGRESS", "version": ops_item.version},
        headers=diana_headers
    )
    assert resp.status_code == 403


def test_05_invalid_workflow_transition_is_rejected(client, auth_headers, db_session):
    member_headers = auth_headers("member@newtonite.io")

    # Item in OPEN status cannot jump straight to RESOLVED or CLOSED
    open_item = db_session.query(WorkItem).filter(WorkItem.status == WorkItemStatus.OPEN).first()

    resp = client.post(
        f"/items/{open_item.id}/transition",
        json={"status": "RESOLVED", "version": open_item.version},
        headers=member_headers
    )
    assert resp.status_code == 422
    assert "Invalid transition" in resp.json()["detail"]


def test_06_valid_lead_approval_for_own_team_succeeds(client, auth_headers, db_session):
    lead_headers = auth_headers("lead@newtonite.io")

    # Item awaiting approval in ops team
    item = db_session.query(WorkItem).filter(WorkItem.status == WorkItemStatus.AWAITING_APPROVAL).first()
    orig_version = item.version

    resp = client.post(
        f"/items/{item.id}/transition",
        json={"status": "RESOLVED", "version": orig_version, "comment": "Approved by Ops Lead"},
        headers=lead_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["version"] == orig_version + 1


def test_08_stale_version_update_returns_409(client, auth_headers, db_session):
    member_headers = auth_headers("member@newtonite.io")
    item = db_session.query(WorkItem).filter(WorkItem.status == WorkItemStatus.IN_PROGRESS).first()

    # Pass stale version
    stale_version = item.version + 99
    resp = client.patch(
        f"/items/{item.id}",
        json={"title": "Updated Title", "version": stale_version},
        headers=member_headers
    )
    assert resp.status_code == 409
    assert "Conflict detected" in resp.json()["detail"]["message"]

    # Verify database record was NOT changed
    db_session.refresh(item)
    assert item.title != "Updated Title"


def test_09_and_11_idempotent_creation_and_payload_conflict(client, auth_headers, db_session):
    member_headers = auth_headers("member@newtonite.io")
    resp_teams = client.get("/teams", headers=member_headers)
    team_id = resp_teams.json()[0]["id"]

    idempotency_key = "unique-client-key-12345"
    payload = {
        "title": "Idempotent Item",
        "description": "Testing idempotency semantics",
        "type": "TASK",
        "priority": "LOW",
        "team_id": team_id
    }

    # 1. First creation
    headers1 = {**member_headers, "Idempotency-Key": idempotency_key}
    resp1 = client.post("/items", json=payload, headers=headers1)
    assert resp1.status_code == 201
    created_id = resp1.json()["id"]

    # 2. Repeated creation with identical key and payload (Replay)
    resp2 = client.post("/items", json=payload, headers=headers1)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == created_id

    # Count items in database with this title - must be strictly 1
    matching_count = db_session.query(WorkItem).filter(WorkItem.title == "Idempotent Item").count()
    assert matching_count == 1

    # 3. Reusing key with different payload must yield 409 Conflict
    conflicting_payload = {**payload, "title": "Tampered Title"}
    resp3 = client.post("/items", json=conflicting_payload, headers=headers1)
    assert resp3.status_code == 409
    assert "Idempotency key reuse detected" in resp3.json()["detail"]


def test_12_failed_mutation_leaves_no_partial_activity_events(client, auth_headers, db_session):
    member_headers = auth_headers("member@newtonite.io")
    item = db_session.query(WorkItem).filter(WorkItem.status == WorkItemStatus.IN_PROGRESS).first()
    initial_activity_count = len(item.activities)

    # Attempt transition that fails (invalid status transition)
    client.post(
        f"/items/{item.id}/transition",
        json={"status": "OPEN", "version": item.version + 99}, # Version conflict
        headers=member_headers
    )

    db_session.refresh(item)
    assert len(item.activities) == initial_activity_count


def test_13_successful_mutations_create_activity_history(client, auth_headers, db_session):
    lead_headers = auth_headers("lead@newtonite.io")
    item = db_session.query(WorkItem).filter(WorkItem.status == WorkItemStatus.AWAITING_APPROVAL).first()

    # Lead resolves item
    resp = client.post(
        f"/items/{item.id}/transition",
        json={"status": "RESOLVED", "version": item.version, "comment": "Signoff complete"},
        headers=lead_headers
    )
    assert resp.status_code == 200

    # Retrieve activity history
    resp_act = client.get(f"/items/{item.id}/activity", headers=lead_headers)
    assert resp_act.status_code == 200
    activities = resp_act.json()
    assert len(activities) > 0
    latest = activities[-1]
    assert latest["action"] == "APPROVED"
    assert latest["after_state"]["status"] == "RESOLVED"
    assert latest["comment"] == "Signoff complete"


def test_14_and_15_outbox_transaction_and_idempotent_processing(client, auth_headers, db_session):
    member_headers = auth_headers("member@newtonite.io")
    resp_teams = client.get("/teams", headers=member_headers)
    team_id = resp_teams.json()[0]["id"]

    # 1. Create item creates outbox message atomically
    initial_outbox_count = db_session.query(OutboxMessage).count()
    resp = client.post(
        "/items",
        json={
            "title": "Outbox Trigger Item",
            "description": "Checking outbox",
            "type": "INCIDENT",
            "priority": "CRITICAL",
            "team_id": team_id
        },
        headers=member_headers
    )
    assert resp.status_code == 201

    new_outbox_count = db_session.query(OutboxMessage).count()
    assert new_outbox_count == initial_outbox_count + 1

    # 2. Worker processes outbox job
    processed = process_outbox_jobs_once(db_session)
    assert processed >= 1

    # 3. Retrying already completed job does not duplicate processing
    reprocessed = process_outbox_jobs_once(db_session)
    assert reprocessed == 0


def test_16_filtering_and_pagination(client, auth_headers):
    lead_headers = auth_headers("lead@newtonite.io")

    # 1. Test pagination limit
    resp = client.get("/items?page=1&limit=2", headers=lead_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["limit"] == 2
    assert data["total"] >= 4

    # 2. Test status filter
    resp = client.get("/items?status=OPEN", headers=lead_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(it["status"] == "OPEN" for it in items)

    # 3. Test text search
    resp = client.get("/items?search=Deadlock", headers=lead_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert "Deadlock" in items[0]["title"]
