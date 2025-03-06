"""create views

Revision ID: d747d5c0f003
Revises: a79f132f2701
Create Date: 2024-11-14 18:20:44.401132

"""
from typing import Sequence, Union

from alembic import op

from python.database.sqlalchemy_main import ReplaceableObject, get_db_dataset

DATASET = get_db_dataset()

# revision identifiers, used by Alembic.
revision: str = 'd747d5c0f003'
down_revision: Union[str, None] = 'a79f132f2701'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


model_config_runs = ReplaceableObject(
    'model_config_runs',
    f'''
        WITH latest_configs AS (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY config_set, config_name ORDER BY created_at DESC) AS rn
            FROM
                {DATASET}.model_configs
        )
        SELECT
            lc.*,
            r.id as model_run_id,
            r.created_at as run_at
        FROM
            latest_configs lc
        INNER JOIN (
            SELECT
                r.model_config_id,
                MAX(r.created_at) AS max_timestamp
            FROM
                {DATASET}.model_runs r
            WHERE
                r.success = TRUE
            GROUP BY
                r.model_config_id
        ) AS latest_run
            ON lc.id = latest_run.model_config_id
        INNER JOIN {DATASET}.model_runs r ON
            lc.id = r.model_config_id AND
            r.created_at = latest_run.max_timestamp
        WHERE
            lc.rn = 1
    '''
)

edes_extra_view = ReplaceableObject(
    'edes_extras',
    f'''
        SELECT
            e.*,
            c.location,
            c.year,
            c.precincts_open,
            c.id as config_id,
            c.config_set,
            c.config_name
        FROM {DATASET}.edes e
        LEFT JOIN {DATASET}.model_config_runs c
            ON e.model_run_id = c.model_run_id
    ''')

precinct_distances_extra_view = ReplaceableObject(
    'precinct_distances_extras',
    f'''
        SELECT
            p.*,
            c.location,
            c.year,
            c.precincts_open,
            c.id as config_id,
            c.config_set,
            c.config_name
        FROM {DATASET}.precinct_distances p
        LEFT JOIN {DATASET}.model_config_runs c
            ON p.model_run_id = c.model_run_id;
    ''')

residence_distances_extra_view = ReplaceableObject(
    'residence_distances_extras',
    f'''
        SELECT
            r.*,
            c.location,
            c.year,
            c.precincts_open,
            c.id as config_id,
            c.config_set,
            c.config_name
        FROM {DATASET}.residence_distances r
        LEFT JOIN {DATASET}.model_config_runs c
            ON r.model_run_id = c.model_run_id
    ''')

result_extra_view = ReplaceableObject(
    'results_extras',
    f'''
        SELECT
            r.*,
            c.location,
            c.year,
            c.precincts_open,
            c.id as config_id,
            c.config_set,
            c.config_name
        FROM {DATASET}.results r
        LEFT JOIN {DATASET}.model_config_runs c
            ON r.model_run_id = c.model_run_id
    ''')


def upgrade() -> None:
    op.create_view(model_config_runs)
    op.create_view(edes_extra_view)
    op.create_view(precinct_distances_extra_view)
    op.create_view(residence_distances_extra_view)
    op.create_view(result_extra_view)


def downgrade() -> None:
    op.drop_view(model_config_runs)
    op.drop_view(edes_extra_view)
    op.drop_view(precinct_distances_extra_view)
    op.drop_view(residence_distances_extra_view)
    op.drop_view(result_extra_view)
