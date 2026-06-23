"""add census_data_type to distance_data_set

Revision ID: b7c4e2a9f1d3
Revises: d33f00f3c168
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c4e2a9f1d3'
down_revision: Union[str, None] = 'd33f00f3c168'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('distance_data_sets', sa.Column('census_data_type', sa.String(256), nullable=True))
    connection = op.get_bind()
    connection.execute(
        sa.text('UPDATE distance_data_sets SET census_data_type = :value WHERE true'),
        {'value': 'redistricting'},
    )


def downgrade() -> None:
    op.drop_column('distance_data_sets', 'census_data_type')
