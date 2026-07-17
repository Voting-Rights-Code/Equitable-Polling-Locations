"""add projection_year to config

Revision ID: 701b8da69145
Revises: d33f00f3c168
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '701b8da69145'
down_revision: Union[str, None] = 'd33f00f3c168'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('model_configs', sa.Column('projection_year', sa.String(256), nullable=True))

def downgrade() -> None:
    op.drop_column('model_configs', 'projection_year')
