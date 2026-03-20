"""rename_polling_locations_only_sets_to_potential_locations_sets

Revision ID: cf2743d9a097
Revises: ea4f1c9c0342
Create Date: 2025-12-11 15:00:50.747731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cf2743d9a097'
down_revision: Union[str, None] = 'ea4f1c9c0342'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    op.execute(sa.text(
        f'ALTER TABLE `{db_dataset}.polling_locations_only_sets` RENAME TO `potential_locations_sets`')
    )


def downgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    op.execute(sa.text(
        f'ALTER TABLE `{db_dataset}.potential_locations_sets` RENAME TO `polling_locations_only_sets`')
    )


