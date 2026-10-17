import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Index,
    JSON,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TeamRole(str, enum.Enum):
    VIEWER = "VIEWER"
    MEMBER = "MEMBER"
    LEAD = "LEAD"
    ADMIN = "ADMIN"


class WorkItemType(str, enum.Enum):
    INCIDENT = "INCIDENT"
    CUSTOMER_ISSUE = "CUSTOMER_ISSUE"
    PAYMENT = "PAYMENT"
    COMPLIANCE = "COMPLIANCE"
    TASK = "TASK"


class WorkItemPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    team_memberships = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")
    created_items = relationship("WorkItem", back_populates="creator", foreign_keys="WorkItem.creator_id")
    assigned_items = relationship("WorkItem", back_populates="assignee", foreign_keys="WorkItem.assignee_id")
    activities = relationship("ActivityLog", back_populates="actor")


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    work_items = relationship("WorkItem", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(TeamRole, name="team_role_enum", native_enum=False), nullable=False, default=TeamRole.MEMBER)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_user_membership"),
    )


class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    type = Column(Enum(WorkItemType, name="work_item_type_enum", native_enum=False), nullable=False, index=True)
    priority = Column(Enum(WorkItemPriority, name="work_item_priority_enum", native_enum=False), nullable=False, index=True)
    status = Column(Enum(WorkItemStatus, name="work_item_status_enum", native_enum=False), nullable=False, default=WorkItemStatus.OPEN, index=True)
    
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    creator_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    due_date = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    team = relationship("Team", back_populates="work_items")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_items")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_items")
    activities = relationship("ActivityLog", back_populates="work_item", cascade="all, delete-orphan", order_by="ActivityLog.created_at.asc()")

    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_work_item_version_positive"),
        Index("ix_work_items_team_status_priority", "team_id", "status", "priority"),
    )


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    work_item_id = Column(String(36), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # CREATED, ASSIGNED, UNASSIGNED, STATUS_CHANGED, PRIORITY_CHANGED, UPDATED, APPROVED
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    work_item = relationship("WorkItem", back_populates="activities")
    actor = relationship("User", back_populates="activities")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    operation = Column(String(100), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_body = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "operation", "idempotency_key", name="uq_idempotency_user_op_key"),
    )


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    status = Column(Enum(OutboxStatus, name="outbox_status_enum", native_enum=False), nullable=False, default=OutboxStatus.PENDING, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    last_error = Column(Text, nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("attempts <= max_attempts", name="ck_outbox_attempts_limit"),
        Index("ix_outbox_pending_jobs", "status", "locked_until", "created_at"),
    )
