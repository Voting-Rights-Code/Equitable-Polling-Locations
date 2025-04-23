"""distance views

Revision ID: 8e4685dd772b
Revises: 4a6823d917dd
Create Date: 2025-02-27 11:05:32.266634

"""
from typing import Sequence, Union

from alembic import op
from python.database.sqlalchemy_main import ReplaceableObject, get_db_dataset


# revision identifiers, used by Alembic.
revision: str = '8e4685dd772b'
down_revision: Union[str, None] = '4a6823d917dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATASET = get_db_dataset()

latest_distance_set_view = ReplaceableObject(
    'latest_distance_sets',
    f'''
        WITH ranked_distance_sets AS (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY location ORDER BY created_at DESC) AS rn
            FROM
                {DATASET}.distance_sets
        )
        SELECT
            rds.*,
        FROM
            ranked_distance_sets rds
        WHERE
            rds.rn = 1
    '''
)

def upgrade() -> None:
    op.create_view(latest_distance_set_view)


def downgrade() -> None:
    op.drop_view(latest_distance_set_view)
