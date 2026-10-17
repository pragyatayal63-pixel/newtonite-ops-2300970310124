import sys
import uuid
from datetime import datetime, timezone, timedelta
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.core.security import get_password_hash
from backend.app.models import (
    User,
    Team,
    TeamMember,
    TeamRole,
    WorkItem,
    WorkItemType,
    WorkItemPriority,
    WorkItemStatus,
    ActivityLog
)


def seed_database(db_session=None):
    close_after = False
    if db_session is None:
        db = SessionLocal()
        close_after = True
    else:
        db = db_session

    try:
        # Clear existing seed data if any
        db.query(ActivityLog).delete()
        db.query(WorkItem).delete()
        db.query(TeamMember).delete()
        db.query(Team).delete()
        db.query(User).delete()
        db.commit()

        # 1. Create Teams
        ops_team = Team(
            id=str(uuid.uuid4()),
            name="Operations Core",
            slug="ops-core",
            description="Core infrastructure, platform stability, and emergency incident triage"
        )
        fin_team = Team(
            id=str(uuid.uuid4()),
            name="Financial Compliance",
            slug="fin-compliance",
            description="Payment disputes, AML reviews, and financial audits"
        )
        db.add_all([ops_team, fin_team])
        db.flush()

        # 2. Create Users across roles
        # Common test password for all seeded users: "Password123!"
        hashed_pw = get_password_hash("Password123!")

        lead_user = User(
            id=str(uuid.uuid4()),
            email="lead@newtonite.io",
            full_name="Alice Ops Lead",
            hashed_password=hashed_pw,
            is_active=1
        )
        member_user = User(
            id=str(uuid.uuid4()),
            email="member@newtonite.io",
            full_name="Bob Ops Member",
            hashed_password=hashed_pw,
            is_active=1
        )
        viewer_user = User(
            id=str(uuid.uuid4()),
            email="viewer@newtonite.io",
            full_name="Charlie Ops Viewer",
            hashed_password=hashed_pw,
            is_active=1
        )
        fin_lead_user = User(
            id=str(uuid.uuid4()),
            email="finlead@newtonite.io",
            full_name="Diana Finance Lead",
            hashed_password=hashed_pw,
            is_active=1
        )

        db.add_all([lead_user, member_user, viewer_user, fin_lead_user])
        db.flush()

        # 3. Create Team Memberships
        db.add_all([
            # Alice is LEAD in Ops Core
            TeamMember(team_id=ops_team.id, user_id=lead_user.id, role=TeamRole.LEAD),
            # Bob is MEMBER in Ops Core
            TeamMember(team_id=ops_team.id, user_id=member_user.id, role=TeamRole.MEMBER),
            # Charlie is VIEWER in Ops Core
            TeamMember(team_id=ops_team.id, user_id=viewer_user.id, role=TeamRole.VIEWER),
            # Diana is LEAD in Financial Compliance (disjoint team)
            TeamMember(team_id=fin_team.id, user_id=fin_lead_user.id, role=TeamRole.LEAD),
        ])
        db.flush()

        # 4. Create Representative Work Items
        now = datetime.now(timezone.utc)
        items = [
            WorkItem(
                id=str(uuid.uuid4()),
                title="Payment Gateway Timeout in EU Region",
                description="Elevated latency observed on Stripe SEPA transactions over 5000ms.",
                type=WorkItemType.INCIDENT,
                priority=WorkItemPriority.CRITICAL,
                status=WorkItemStatus.OPEN,
                team_id=ops_team.id,
                creator_id=lead_user.id,
                assignee_id=None,
                due_date=now + timedelta(hours=4),
                version=1
            ),
            WorkItem(
                id=str(uuid.uuid4()),
                title="Database Deadlock on Ledger Reconciliations",
                description="Simultaneous nightly batch jobs conflicting with real-time settlement lock.",
                type=WorkItemType.INCIDENT,
                priority=WorkItemPriority.HIGH,
                status=WorkItemStatus.IN_PROGRESS,
                team_id=ops_team.id,
                creator_id=member_user.id,
                assignee_id=member_user.id,
                due_date=now + timedelta(days=1),
                version=1
            ),
            WorkItem(
                id=str(uuid.uuid4()),
                title="Q3 AML Sanction Screening Audit Approval",
                description="Compliance audit checklist complete. Pending lead signoff before submitting to regulators.",
                type=WorkItemType.COMPLIANCE,
                priority=WorkItemPriority.HIGH,
                status=WorkItemStatus.AWAITING_APPROVAL,
                team_id=ops_team.id,
                creator_id=member_user.id,
                assignee_id=member_user.id,
                due_date=now + timedelta(days=2),
                version=1
            ),
            WorkItem(
                id=str(uuid.uuid4()),
                title="Update SSL Certificates for API Ingress",
                description="Rotate wildcard certificate on Kubernetes ingress gateway.",
                type=WorkItemType.TASK,
                priority=WorkItemPriority.MEDIUM,
                status=WorkItemStatus.RESOLVED,
                team_id=ops_team.id,
                creator_id=lead_user.id,
                assignee_id=lead_user.id,
                due_date=now + timedelta(days=5),
                version=2
            ),
            WorkItem(
                id=str(uuid.uuid4()),
                title="Merchant Chargeback Threshold Review",
                description="Monthly dispute volume exceeded 0.9% for high-risk merchant account.",
                type=WorkItemType.PAYMENT,
                priority=WorkItemPriority.MEDIUM,
                status=WorkItemStatus.OPEN,
                team_id=fin_team.id,
                creator_id=fin_lead_user.id,
                assignee_id=None,
                due_date=now + timedelta(days=3),
                version=1
            ),
        ]
        db.add_all(items)
        db.commit()
        print("Database seeded successfully with teams, users, and work items!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        if close_after:
            db.close()


if __name__ == "__main__":
    seed_database()
