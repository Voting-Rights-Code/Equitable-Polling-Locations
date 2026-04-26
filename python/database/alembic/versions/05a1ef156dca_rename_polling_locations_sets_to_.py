"""rename_polling_locations_sets_to_distance_data_sets

Revision ID: 05a1ef156dca
Revises: 5d5706c75d62
Create Date: 2025-12-11 17:02:06.040903

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '05a1ef156dca'
down_revision: Union[str, None] = '5d5706c75d62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    # Note: RENAME COLUMN has to happen first, doing the other way around
    # causes the column rename to fail sliently
    op.execute(
        f'ALTER TABLE `{db_dataset}.polling_locations_sets` '
        f'RENAME COLUMN `locations_only_set_id` TO `potential_locations_set_id`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.polling_locations_sets` RENAME TO `distance_data_sets`'
    )


def downgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    # Note: RENAME COLUMN has to happen first, doing the other way around
    # causes the column rename to fail sliently
    op.execute(
        f'ALTER TABLE `{db_dataset}.distance_data_sets` '
        f'RENAME COLUMN `potential_locations_set_id` TO `locations_only_set_id`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.distance_data_sets` RENAME TO `polling_locations_sets`'
    )
