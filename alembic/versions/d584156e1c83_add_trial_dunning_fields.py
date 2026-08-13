"""add_trial_dunning_fields

Revision ID: d584156e1c83
Revises: 96411cf92a3b
Create Date: 2026-06-26 19:53:43.246973

NOTE: SQLite does not support ALTER COLUMN TYPE, so any type-mismatch
fixes detected by autogenerate must be done manually or via batch mode.
The publish_history.user_id INTEGER→String mismatch is pre-existing and
harmless under SQLite's flexible typing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd584156e1c83'
down_revision: Union[str, Sequence[str], None] = '96411cf92a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('webhook_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('payload', sa.Text(), nullable=True),
    sa.Column('processed', sa.Boolean(), nullable=True),
    sa.Column('error', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'event_id', name='uq_webhook_event_source_id')
    )
    op.add_column('users', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('dunning_count', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('last_dunning_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_dunning_at')
    op.drop_column('users', 'dunning_count')
    op.drop_column('users', 'trial_ends_at')
    op.drop_table('webhook_events')
