"""add census_data_type to config

Revision ID: d33f00f3c168
Revises: 25c563b5a292
Create Date: 2026-05-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd33f00f3c168'
down_revision: Union[str, None] = '25c563b5a292'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('model_configs', sa.Column('census_data_type', sa.String(256), nullable=True))
    connection = op.get_bind()
    connection.execute(
        sa.text('UPDATE model_configs SET census_data_type = :value WHERE true'),
        {'value': 'redistricting'},
    )

def downgrade() -> None:
    op.drop_column('model_configs', 'census_data_type')
