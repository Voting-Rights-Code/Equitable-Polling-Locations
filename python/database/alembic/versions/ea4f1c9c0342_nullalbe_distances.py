"""nullalbe distances

Revision ID: ea4f1c9c0342
Revises: e5a21f261532
Create Date: 2025-05-15 14:33:15.891355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea4f1c9c0342'
down_revision: Union[str, None] = 'e5a21f261532'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('polling_locations', 'distance_m',
        existing_type=sa.Float(),
        nullable=True
    )


def downgrade() -> None:
    op.alter_column('polling_locations', 'distance_m',
        existing_type=sa.Float(),
        nullable=False
    )
