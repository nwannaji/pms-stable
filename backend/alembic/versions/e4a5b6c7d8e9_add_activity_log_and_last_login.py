"""add activity_logs table and users.last_login

Revision ID: e4a5b6c7d8e9
Revises: b2e4f1a8c7d3
Create Date: 2026-09-16 00:01:00.000000

Adds:
  - activity_logs: user activity audit trail for analytics/reporting
  - activityaction: enum type for the action column
  - users.last_login: timestamp of the most recent successful login
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from models import ActivityAction  # noqa: E402 - shared enum definition

revision: str = 'e4a5b6c7d8e9'
down_revision: str = 'b2e4f1a8c7d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'activity_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('action', sa.Enum(ActivityAction, name='activityaction',
                                    create_type=True, native_enum=True),
                  nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', UUID(as_uuid=True), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_activity_logs_id', 'activity_logs', ['id'])
    op.create_index('ix_activity_logs_action', 'activity_logs', ['action'])
    op.create_index('ix_activity_logs_created_at', 'activity_logs', ['created_at'])
    op.create_index('ix_activity_user_time', 'activity_logs',
                    ['user_id', 'created_at'])
    op.create_index('ix_activity_action_time', 'activity_logs',
                    ['action', 'created_at'])

    op.add_column(
        'users',
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'last_login')
    op.drop_index('ix_activity_action_time', table_name='activity_logs')
    op.drop_index('ix_activity_user_time', table_name='activity_logs')
    op.drop_index('ix_activity_logs_created_at', table_name='activity_logs')
    op.drop_index('ix_activity_logs_action', table_name='activity_logs')
    op.drop_index('ix_activity_logs_id', table_name='activity_logs')
    op.drop_table('activity_logs')
    op.execute("DROP TYPE IF EXISTS activityaction")