"""location views

Revision ID: 7b823481f2fc
Revises: 35d8933be76a
Create Date: 2025-04-02 15:47:56.228105

"""
from typing import Sequence, Union

from alembic import op
from python.database.sqlalchemy_main import ReplaceableObject, get_db_dataset


# revision identifiers, used by Alembic.
revision: str = '7b823481f2fc'
down_revision: Union[str, None] = '35d8933be76a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATASET = get_db_dataset()

latest_locations_set_view = ReplaceableObject(
    'latest_location_sets',
    f'''
        WITH ranked_location_sets AS (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY location ORDER BY created_at DESC) AS rn
            FROM
                {DATASET}.polling_locations_sets
        )
        SELECT
            rds.*,
        FROM
            ranked_location_sets rds
        WHERE
            rds.rn = 1
    '''
)

def upgrade() -> None:
    op.create_view(latest_locations_set_view)


def downgrade() -> None:
    op.drop_view(latest_locations_set_view)
