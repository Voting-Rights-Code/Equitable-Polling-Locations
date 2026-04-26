"""add limits_gap to config

Revision ID: 25c563b5a292
Revises: 025192210ae9
Create Date: 2026-01-21 15:10:30.892618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25c563b5a292'
down_revision: Union[str, None] = '025192210ae9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('model_configs', sa.Column('limits_gap', sa.Float(), nullable=True))
    connection = op.get_bind()
    connection.execute(sa.text('UPDATE model_configs SET limits_gap = :value WHERE true'), {'value': 0.02})

def downgrade() -> None:
    op.drop_column('model_configs', 'limits_gap')
