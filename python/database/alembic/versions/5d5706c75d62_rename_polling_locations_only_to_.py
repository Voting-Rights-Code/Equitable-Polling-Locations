"""rename_polling_locations_only_to_potential_locations

Revision ID: 5d5706c75d62
Revises: cf2743d9a097
Create Date: 2025-12-11 15:09:00.128986

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5d5706c75d62'
down_revision: Union[str, None] = 'cf2743d9a097'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    # Note: RENAME COLUMN has to happen first, doing the other way around
    # causes the column rename to fail sliently
    op.execute(
        f'ALTER TABLE `{db_dataset}.polling_locations_only` '
        f'RENAME COLUMN `locations_only_set_id` TO `potential_locations_set_id`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.polling_locations_only` RENAME TO `potential_locations`'
    )


def downgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    # Note: RENAME COLUMN has to happen first, doing the other way around
    # causes the column rename to fail sliently
    op.execute(
        f'ALTER TABLE `{db_dataset}.potential_locations` '
        f'RENAME COLUMN `potential_locations_set_id` TO `locations_only_set_id`'
    )

    op.execute(
        f'ALTER TABLE `{db_dataset}.potential_locations` RENAME TO `polling_locations_only`'
    )



