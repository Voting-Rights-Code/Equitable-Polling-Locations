"""create views

Revision ID: d747d5c0f003
Revises: a79f132f2701
Create Date: 2024-11-14 18:20:44.401132

"""
from typing import Sequence, Union

from alembic import op

from python.database.sqlalchemy_main import ReplaceableObject

# revision identifiers, used by Alembic.
revision: str = 'd747d5c0f003'
down_revision: Union[str, None] = 'a79f132f2701'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def build_model_config_runs(db_dataset: str) -> ReplaceableObject:
    return ReplaceableObject(
        'model_config_runs',
        f'''
            WITH latest_configs AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY config_set, config_name ORDER BY created_at DESC) AS rn
                FROM
                    {db_dataset}.model_configs
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
                    {db_dataset}.model_runs r
                WHERE
                    r.success = TRUE
                GROUP BY
                    r.model_config_id
            ) AS latest_run
                ON lc.id = latest_run.model_config_id
            INNER JOIN {db_dataset}.model_runs r ON
                lc.id = r.model_config_id AND
                r.created_at = latest_run.max_timestamp
            WHERE
                lc.rn = 1
        '''
    )

def build_edes_extra_view(db_dataset: str) -> ReplaceableObject:
    return ReplaceableObject(
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
            FROM {db_dataset}.edes e
            LEFT JOIN {db_dataset}.model_config_runs c
                ON e.model_run_id = c.model_run_id
        '''
    )

def build_precinct_distances_extra_view(db_dataset: str) -> ReplaceableObject:
    return ReplaceableObject(
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
            FROM {db_dataset}.precinct_distances p
            LEFT JOIN {db_dataset}.model_config_runs c
                ON p.model_run_id = c.model_run_id;
        '''
    )

def build_residence_distances_extra_view(db_dataset: str) -> ReplaceableObject:
    return ReplaceableObject(
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
            FROM {db_dataset}.residence_distances r
            LEFT JOIN {db_dataset}.model_config_runs c
                ON r.model_run_id = c.model_run_id
        '''
    )

def build_result_extra_view(db_dataset: str) -> ReplaceableObject:
    return ReplaceableObject(
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
            FROM {db_dataset}.results r
            LEFT JOIN {db_dataset}.model_config_runs c
                ON r.model_run_id = c.model_run_id
        '''
    )


def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    op.create_view(build_model_config_runs(db_dataset))
    op.create_view(build_edes_extra_view(db_dataset))
    op.create_view(build_precinct_distances_extra_view(db_dataset))
    op.create_view(build_residence_distances_extra_view(db_dataset))
    op.create_view(build_result_extra_view(db_dataset))


def downgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')

    op.drop_view(build_model_config_runs(db_dataset))
    op.drop_view(build_edes_extra_view(db_dataset))
    op.drop_view(build_precinct_distances_extra_view(db_dataset))
    op.drop_view(build_residence_distances_extra_view(db_dataset))
    op.drop_view(build_result_extra_view(db_dataset))
