"""locations

Revision ID: 35d8933be76a
Revises: 8e4685dd772b
Create Date: 2025-04-01 17:13:08.339709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35d8933be76a'
down_revision: Union[str, None] = '8e4685dd772b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('polling_locations_sets',
    sa.Column('id', sa.String(length=36), server_default=sa.text('GENERATE_UUID()'), nullable=False),
    sa.Column('location', sa.String(length=256), nullable=False),
    sa.Column('election_year', sa.String(length=4), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('polling_locations',
    sa.Column('id', sa.String(length=36), server_default=sa.text('GENERATE_UUID()'), nullable=False),
    sa.Column('id_orig', sa.String(length=256), nullable=False),
    sa.Column('id_dest', sa.String(length=256), nullable=False),
    sa.Column('distance_m', sa.Float(), nullable=False),
    sa.Column('address', sa.String(length=256), nullable=False),
    sa.Column('dest_lat', sa.Float(), nullable=False),
    sa.Column('dest_lon', sa.Float(), nullable=False),
    sa.Column('orig_lat', sa.Float(), nullable=False),
    sa.Column('orig_lon', sa.Float(), nullable=False),
    sa.Column('location_type', sa.String(length=256), nullable=False),
    sa.Column('dest_type', sa.String(length=256), nullable=False),
    sa.Column('population', sa.Integer(), nullable=False),
    sa.Column('hispanic', sa.Integer(), nullable=False),
    sa.Column('non_hispanic', sa.Integer(), nullable=False),
    sa.Column('white', sa.Integer(), nullable=False),
    sa.Column('black', sa.Integer(), nullable=False),
    sa.Column('native', sa.Integer(), nullable=False),
    sa.Column('asian', sa.Integer(), nullable=False),
    sa.Column('pacific_islander', sa.Integer(), nullable=False),
    sa.Column('other', sa.Integer(), nullable=False),
    sa.Column('multiple_races', sa.Integer(), nullable=False),
    sa.Column('log_distance', sa.Boolean(), nullable=False),
    sa.Column('driving', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=256), nullable=False),
    sa.Column('polling_locations_set_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['polling_locations_set_id'], ['polling_locations_sets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('polling_locations_only',
    sa.Column('id', sa.String(length=36), server_default=sa.text('GENERATE_UUID()'), nullable=False),
    sa.Column('location', sa.String(length=256), nullable=False),
    sa.Column('address', sa.String(length=256), nullable=False),
    sa.Column('location_type', sa.String(length=256), nullable=False),
    sa.Column('lat_lon', sa.String(length=256), nullable=False),
    sa.Column('polling_locations_set_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['polling_locations_set_id'], ['polling_locations_sets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('polling_locations_only')
    op.drop_table('polling_locations')
    op.drop_table('polling_locations_sets')
