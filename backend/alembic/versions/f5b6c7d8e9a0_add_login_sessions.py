"""add login_sessions table

Revision ID: f5b6c7d8e9a0
Revises: e4a5b6c7d8e9
Create Date: 2026-09-17 13:00:00.000000

Adds:
  - login_sessions: one row per platform login; the heartbeat endpoint keeps
    last_active_at fresh and session duration is computed at read time
    (COALESCE(logout_at, last_active_at) - login_at). Purely additive.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'f5b6c7d8e9a0'
down_revision: str = 'e4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'login_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('organization_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_name', sa.String(255), nullable=True),
        sa.Column('login_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('logout_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_reason', sa.String(20), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
    )
    op.create_index('ix_login_sessions_id', 'login_sessions', ['id'])
    op.create_index('ix_login_sessions_login_at', 'login_sessions', ['login_at'])
    op.create_index('ix_login_sessions_user_time', 'login_sessions',
                    ['user_id', 'login_at'])
    op.create_index('ix_login_sessions_open', 'login_sessions', ['user_id'],
                    postgresql_where=sa.text('logout_at IS NULL'))


def downgrade() -> None:
    op.drop_index('ix_login_sessions_open', table_name='login_sessions')
    op.drop_index('ix_login_sessions_user_time', table_name='login_sessions')
    op.drop_index('ix_login_sessions_login_at', table_name='login_sessions')
    op.drop_index('ix_login_sessions_id', table_name='login_sessions')
    op.drop_table('login_sessions')