"""rename_polling_locations_to_distance_data

Revision ID: 025192210ae9
Revises: 05a1ef156dca
Create Date: 2025-12-11 17:29:51.174285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '025192210ae9'
down_revision: Union[str, None] = '05a1ef156dca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    # Note: RENAME COLUMN has to happen first, doing the other way around
    # causes the column rename to fail sliently
    op.execute(
        f'ALTER TABLE `{db_dataset}.polling_locations`'
        f'RENAME COLUMN `polling_locations_set_id` TO `distance_data_set_id`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.polling_locations` RENAME TO `distance_data`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.model_runs`'
        f'RENAME COLUMN `polling_locations_set_id` TO `distance_data_set_id`'
    )


def downgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    # Note: RENAME COLUMN has to happen first, doing the other way around
    # causes the column rename to fail sliently
    op.execute(
        f'ALTER TABLE `{db_dataset}.model_runs`'
        f'RENAME COLUMN `distance_data_set_id` TO `polling_locations_set_id`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.distance_data` '
        f'RENAME COLUMN `distance_data_set_id` TO `polling_locations_set_id`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.distance_data` RENAME TO `polling_locations`'
    )
