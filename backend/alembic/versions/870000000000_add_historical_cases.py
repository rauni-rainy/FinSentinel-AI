"""add_historical_cases

Revision ID: 870000000000
Revises: cef2b97f0d44
Create Date: 2026-08-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '870000000000'
down_revision: Union[str, None] = 'cef2b97f0d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IMPORTANT: Create the vector extension first!
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('historical_cases',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('transaction_id', sa.String(), nullable=True),
    sa.Column('summary', sa.String(), nullable=True),
    sa.Column('is_fraud', sa.Boolean(), nullable=True),
    sa.Column('embedding', Vector(dim=1536), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_historical_cases_transaction_id'), 'historical_cases', ['transaction_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_historical_cases_transaction_id'), table_name='historical_cases')
    op.drop_table('historical_cases')
