"""add driving_time metric and duration_s columns

Revision ID: d1f2a3b4c5d6
Revises: 25c563b5a292
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f2a3b4c5d6'
down_revision: Union[str, None] = '25c563b5a292'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('model_configs', sa.Column('metric', sa.String(length=256), nullable=True))
    op.add_column('driving_distances', sa.Column('duration_s', sa.Float(), nullable=True))
    op.add_column('distance_data', sa.Column('duration_s', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('distance_data', 'duration_s')
    op.drop_column('driving_distances', 'duration_s')
    op.drop_column('model_configs', 'metric')
