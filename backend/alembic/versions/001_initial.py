"""initial_migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-10-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Teams
    op.create_table(
        'teams',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teams_slug'), 'teams', ['slug'], unique=True)

    # Team Members
    op.create_table(
        'team_members',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('team_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_team_user_membership')
    )
    op.create_index(op.f('ix_team_members_team_id'), 'team_members', ['team_id'], unique=False)
    op.create_index(op.f('ix_team_members_user_id'), 'team_members', ['user_id'], unique=False)

    # Work Items
    op.create_table(
        'work_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('team_id', sa.String(length=36), nullable=False),
        sa.Column('assignee_id', sa.String(length=36), nullable=True),
        sa.Column('creator_id', sa.String(length=36), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('version >= 1', name='ck_work_item_version_positive'),
        sa.ForeignKeyConstraint(['assignee_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_work_items_title'), 'work_items', ['title'], unique=False)
    op.create_index(op.f('ix_work_items_type'), 'work_items', ['type'], unique=False)
    op.create_index(op.f('ix_work_items_priority'), 'work_items', ['priority'], unique=False)
    op.create_index(op.f('ix_work_items_status'), 'work_items', ['status'], unique=False)
    op.create_index(op.f('ix_work_items_team_id'), 'work_items', ['team_id'], unique=False)
    op.create_index(op.f('ix_work_items_assignee_id'), 'work_items', ['assignee_id'], unique=False)
    op.create_index(op.f('ix_work_items_creator_id'), 'work_items', ['creator_id'], unique=False)
    op.create_index(op.f('ix_work_items_created_at'), 'work_items', ['created_at'], unique=False)
    op.create_index('ix_work_items_team_status_priority', 'work_items', ['team_id', 'status', 'priority'], unique=False)

    # Activity Logs
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('work_item_id', sa.String(length=36), nullable=False),
        sa.Column('actor_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('before_state', sa.JSON(), nullable=True),
        sa.Column('after_state', sa.JSON(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['work_item_id'], ['work_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activity_logs_work_item_id'), 'activity_logs', ['work_item_id'], unique=False)
    op.create_index(op.f('ix_activity_logs_actor_id'), 'activity_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_activity_logs_action'), 'activity_logs', ['action'], unique=False)
    op.create_index(op.f('ix_activity_logs_created_at'), 'activity_logs', ['created_at'], unique=False)

    # Idempotency Records
    op.create_table(
        'idempotency_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('operation', sa.String(length=100), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_body', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'operation', 'idempotency_key', name='uq_idempotency_user_op_key')
    )
    op.create_index(op.f('ix_idempotency_records_user_id'), 'idempotency_records', ['user_id'], unique=False)

    # Outbox Messages
    op.create_table(
        'outbox_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('attempts <= max_attempts', name='ck_outbox_attempts_limit'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outbox_messages_job_type'), 'outbox_messages', ['job_type'], unique=False)
    op.create_index(op.f('ix_outbox_messages_status'), 'outbox_messages', ['status'], unique=False)
    op.create_index(op.f('ix_outbox_messages_created_at'), 'outbox_messages', ['created_at'], unique=False)
    op.create_index(op.f('ix_outbox_messages_locked_until'), 'outbox_messages', ['locked_until'], unique=False)
    op.create_index('ix_outbox_pending_jobs', 'outbox_messages', ['status', 'locked_until', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('outbox_messages')
    op.drop_table('idempotency_records')
    op.drop_table('activity_logs')
    op.drop_table('work_items')
    op.drop_table('team_members')
    op.drop_table('teams')
    op.drop_table('users')
