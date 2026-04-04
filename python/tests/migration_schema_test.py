"""Tests for migration schema validator."""
import os

from python.tests.migration_schema_validator import (
    SchemaState, get_revision_info, build_migration_chain,
    extract_operations, validate_migration_chain,
)

VERSIONS_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'database', 'alembic', 'versions'
)


class TestSchemaStateCreateTable:
    """Tests for SchemaState.create_table."""

    def test_create_table_adds_table_and_columns(self):
        schema = SchemaState()
        schema.create_table('users', {'id', 'name', 'email'}, 'rev_001')
        assert 'users' in schema.tables
        assert schema.tables['users'] == {'id', 'name', 'email'}

    def test_create_table_duplicate_records_error(self):
        schema = SchemaState()
        schema.create_table('users', {'id'}, 'rev_001')
        schema.create_table('users', {'id'}, 'rev_002')
        assert len(schema.errors) == 1
        assert 'already exists' in schema.errors[0]


class TestSchemaStateDropTable:
    """Tests for SchemaState.drop_table."""

    def test_drop_table_removes_table(self):
        schema = SchemaState()
        schema.create_table('users', {'id'}, 'rev_001')
        schema.drop_table('users', 'rev_002')
        assert 'users' not in schema.tables

    def test_drop_nonexistent_table_records_error(self):
        schema = SchemaState()
        schema.drop_table('users', 'rev_001')
        assert len(schema.errors) == 1
        assert 'does not exist' in schema.errors[0]


class TestSchemaStateAddColumn:
    """Tests for SchemaState.add_column."""

    def test_add_column_to_existing_table(self):
        schema = SchemaState()
        schema.create_table('users', {'id'}, 'rev_001')
        schema.add_column('users', 'email', 'rev_002')
        assert 'email' in schema.tables['users']

    def test_add_column_to_nonexistent_table_records_error(self):
        schema = SchemaState()
        schema.add_column('users', 'email', 'rev_001')
        assert len(schema.errors) == 1
        assert 'does not exist' in schema.errors[0]

    def test_add_duplicate_column_records_error(self):
        schema = SchemaState()
        schema.create_table('users', {'id'}, 'rev_001')
        schema.add_column('users', 'id', 'rev_002')
        assert len(schema.errors) == 1
        assert 'already exists' in schema.errors[0]


class TestSchemaStateDropColumn:
    """Tests for SchemaState.drop_column."""

    def test_drop_column_removes_column(self):
        schema = SchemaState()
        schema.create_table('users', {'id', 'email'}, 'rev_001')
        schema.drop_column('users', 'email', 'rev_002')
        assert 'email' not in schema.tables['users']

    def test_drop_column_from_nonexistent_table_records_error(self):
        schema = SchemaState()
        schema.drop_column('users', 'email', 'rev_001')
        assert len(schema.errors) == 1

    def test_drop_nonexistent_column_records_error(self):
        schema = SchemaState()
        schema.create_table('users', {'id'}, 'rev_001')
        schema.drop_column('users', 'email', 'rev_002')
        assert len(schema.errors) == 1
        assert 'does not exist' in schema.errors[0]


class TestSchemaStateAlterColumn:
    """Tests for SchemaState.alter_column."""

    def test_alter_column_on_existing_table_and_column(self):
        schema = SchemaState()
        schema.create_table('users', {'id', 'email'}, 'rev_001')
        schema.alter_column('users', 'email', 'rev_002')
        assert len(schema.errors) == 0

    def test_alter_column_on_nonexistent_table_records_error(self):
        schema = SchemaState()
        schema.alter_column('users', 'email', 'rev_001')
        assert len(schema.errors) == 1

    def test_alter_column_on_nonexistent_column_records_error(self):
        schema = SchemaState()
        schema.create_table('users', {'id'}, 'rev_001')
        schema.alter_column('users', 'email', 'rev_002')
        assert len(schema.errors) == 1


class TestSchemaStateRenameTable:
    """Tests for SchemaState.rename_table."""

    def test_rename_table_updates_name(self):
        schema = SchemaState()
        schema.create_table('old_name', {'id'}, 'rev_001')
        schema.rename_table('old_name', 'new_name', 'rev_002')
        assert 'old_name' not in schema.tables
        assert 'new_name' in schema.tables
        assert schema.tables['new_name'] == {'id'}

    def test_rename_nonexistent_table_records_error(self):
        schema = SchemaState()
        schema.rename_table('old_name', 'new_name', 'rev_001')
        assert len(schema.errors) == 1
        assert 'does not exist' in schema.errors[0]

    def test_rename_to_existing_name_records_error(self):
        schema = SchemaState()
        schema.create_table('table_a', {'id'}, 'rev_001')
        schema.create_table('table_b', {'id'}, 'rev_001')
        schema.rename_table('table_a', 'table_b', 'rev_002')
        assert len(schema.errors) == 1
        assert 'already exists' in schema.errors[0]


class TestSchemaStateRenameColumn:
    """Tests for SchemaState.rename_column."""

    def test_rename_column_updates_name(self):
        schema = SchemaState()
        schema.create_table('users', {'id', 'old_col'}, 'rev_001')
        schema.rename_column('users', 'old_col', 'new_col', 'rev_002')
        assert 'old_col' not in schema.tables['users']
        assert 'new_col' in schema.tables['users']

    def test_rename_column_on_nonexistent_table_records_error(self):
        schema = SchemaState()
        schema.rename_column('users', 'old_col', 'new_col', 'rev_001')
        assert len(schema.errors) == 1

    def test_rename_nonexistent_column_records_error(self):
        schema = SchemaState()
        schema.create_table('users', {'id'}, 'rev_001')
        schema.rename_column('users', 'old_col', 'new_col', 'rev_002')
        assert len(schema.errors) == 1
        assert 'does not exist' in schema.errors[0]

    def test_rename_to_existing_column_records_error(self):
        schema = SchemaState()
        schema.create_table('users', {'id', 'old_col'}, 'rev_001')
        schema.rename_column('users', 'old_col', 'id', 'rev_002')
        assert len(schema.errors) == 1
        assert 'already exists' in schema.errors[0]


class TestSchemaStateViews:
    """Tests for SchemaState view tracking."""

    def test_create_view(self):
        schema = SchemaState()
        schema.create_view('my_view', 'rev_001')
        assert 'my_view' in schema.views

    def test_drop_view(self):
        schema = SchemaState()
        schema.create_view('my_view', 'rev_001')
        schema.drop_view('my_view', 'rev_002')
        assert 'my_view' not in schema.views

    def test_drop_nonexistent_view_records_error(self):
        schema = SchemaState()
        schema.drop_view('my_view', 'rev_001')
        assert len(schema.errors) == 1


class TestGetRevisionInfo:
    """Tests for extracting revision metadata from migration files."""

    def test_extracts_revision_and_down_revision(self, tmp_path):
        migration = tmp_path / 'test_migration.py'
        migration.write_text(
            'revision: str = "abc123"\n'
            'down_revision = "def456"\n'
            'def upgrade() -> None:\n'
            '    pass\n'
        )
        info = get_revision_info(str(migration))
        assert info['revision'] == 'abc123'
        assert info['down_revision'] == 'def456'

    def test_handles_none_down_revision(self, tmp_path):
        migration = tmp_path / 'test_migration.py'
        migration.write_text(
            'from typing import Union\n'
            'revision: str = "abc123"\n'
            'down_revision: Union[str, None] = None\n'
            'def upgrade() -> None:\n'
            '    pass\n'
        )
        info = get_revision_info(str(migration))
        assert info['revision'] == 'abc123'
        assert info['down_revision'] is None


class TestBuildMigrationChain:
    """Tests for building an ordered migration chain."""

    def test_builds_chain_from_real_migrations(self):
        chain = build_migration_chain(VERSIONS_DIR)
        # First migration has no down_revision
        assert chain[0]['down_revision'] is None
        # Chain is contiguous — each revision's down_revision matches the previous
        for i in range(1, len(chain)):
            assert chain[i]['down_revision'] == chain[i - 1]['revision']

    def test_chain_includes_all_migration_files(self):
        chain = build_migration_chain(VERSIONS_DIR)
        migration_files = [
            f for f in os.listdir(VERSIONS_DIR) if f.endswith('.py')
        ]
        assert len(chain) == len(migration_files)


class TestExtractOperationsCreateTable:
    """Tests for extracting create_table operations from migration source."""

    def test_extracts_create_table_with_columns(self):
        source = '''
def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'create_table'
        assert operations[0]['table'] == 'users'
        assert operations[0]['columns'] == {'id', 'name'}


class TestExtractOperationsAddColumn:
    """Tests for extracting add_column operations."""

    def test_extracts_add_column(self):
        source = '''
def upgrade() -> None:
    op.add_column('model_configs', sa.Column('log_distance', sa.Boolean(), nullable=True))
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'add_column'
        assert operations[0]['table'] == 'model_configs'
        assert operations[0]['column'] == 'log_distance'


class TestExtractOperationsDropColumn:
    """Tests for extracting drop_column operations."""

    def test_extracts_drop_column(self):
        source = '''
def upgrade() -> None:
    op.drop_column('model_runs', 'polling_locations_set_id')
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'drop_column'
        assert operations[0]['table'] == 'model_runs'
        assert operations[0]['column'] == 'polling_locations_set_id'


class TestExtractOperationsAlterColumn:
    """Tests for extracting alter_column operations."""

    def test_extracts_alter_column(self):
        source = '''
def upgrade() -> None:
    op.alter_column('polling_locations', 'distance_m',
        existing_type=sa.Float(),
        nullable=True
    )
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'alter_column'
        assert operations[0]['table'] == 'polling_locations'
        assert operations[0]['column'] == 'distance_m'


class TestExtractOperationsDropTable:
    """Tests for extracting drop_table operations."""

    def test_extracts_drop_table(self):
        source = '''
def upgrade() -> None:
    op.drop_table('old_table')
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'drop_table'
        assert operations[0]['table'] == 'old_table'


class TestExtractOperationsRenameTable:
    """Tests for extracting RENAME TABLE from raw SQL execute calls."""

    def test_extracts_rename_table_from_fstring_execute(self):
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
    op.execute(
        f'ALTER TABLE `{db_dataset}.old_table` RENAME TO `new_table`'
    )
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'rename_table'
        assert operations[0]['old_name'] == 'old_table'
        assert operations[0]['new_name'] == 'new_table'

    def test_extracts_rename_table_from_sa_text_execute(self):
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
    op.execute(sa.text(
        f'ALTER TABLE `{db_dataset}.old_table` RENAME TO `new_table`')
    )
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'rename_table'
        assert operations[0]['old_name'] == 'old_table'
        assert operations[0]['new_name'] == 'new_table'


class TestExtractOperationsRenameColumn:
    """Tests for extracting RENAME COLUMN from raw SQL execute calls."""

    def test_extracts_rename_column_from_fstring(self):
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
    op.execute(
        f'ALTER TABLE `{db_dataset}.my_table` '
        f'RENAME COLUMN `old_col` TO `new_col`'
    )
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'rename_column'
        assert operations[0]['table'] == 'my_table'
        assert operations[0]['old_column'] == 'old_col'
        assert operations[0]['new_column'] == 'new_col'

    def test_extracts_rename_column_without_space_between_strings(self):
        """Catches the missing-space bug in implicit string concatenation."""
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
    op.execute(
        f'ALTER TABLE `{db_dataset}.my_table`'
        f'RENAME COLUMN `old_col` TO `new_col`'
    )
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'rename_column'
        assert operations[0]['table'] == 'my_table'
        assert operations[0]['old_column'] == 'old_col'
        assert operations[0]['new_column'] == 'new_col'


class TestExtractOperationsRenameColumnAndTable:
    """Tests for migrations with both column and table renames."""

    def test_extracts_both_column_rename_and_table_rename(self):
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
    op.execute(
        f'ALTER TABLE `{db_dataset}.my_table` '
        f'RENAME COLUMN `old_col` TO `new_col`'
    )
    op.execute(
        f'ALTER TABLE `{db_dataset}.my_table` RENAME TO `new_table`'
    )
'''
        operations = extract_operations(source)
        assert len(operations) == 2
        assert operations[0]['type'] == 'rename_column'
        assert operations[1]['type'] == 'rename_table'


class TestExtractOperationsViews:
    """Tests for extracting view operations."""

    def test_extracts_create_view(self):
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
    op.create_view(build_my_view(db_dataset))
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'create_view'
        assert operations[0]['view'] == 'my_view'

    def test_extracts_create_view_from_variable(self):
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
    my_view = build_some_view(db_dataset)
    op.create_view(my_view)
'''
        operations = extract_operations(source)
        assert len(operations) == 1
        assert operations[0]['type'] == 'create_view'


class TestExtractOperationsIgnoresNonSchemaOps:
    """Tests that non-schema operations are correctly ignored."""

    def test_ignores_update_statements(self):
        source = '''
def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text('UPDATE model_configs SET census_year = :value WHERE true'), {'value': '2020'})
'''
        operations = extract_operations(source)
        assert len(operations) == 0

    def test_ignores_config_retrieval(self):
        source = '''
def upgrade() -> None:
    config = op.get_context().config
    db_dataset = config.get_main_option('DB_DATASET')
'''
        operations = extract_operations(source)
        assert len(operations) == 0


class TestMigrationChainValidation:
    """Integration test: validate the real migration chain's schema consistency."""

    def test_migration_chain_schema_is_consistent(self):
        """Walk every migration in chain order and verify all operations
        reference tables and columns that exist at that point in the chain.

        This catches bugs like:
        - Renaming a column that doesn't exist (wrong name or already renamed)
        - Adding a column to a table that was renamed in a previous migration
        - Dropping a table that was already dropped
        """
        errors = validate_migration_chain(VERSIONS_DIR)
        assert not errors, (
            'Migration chain has schema consistency errors:\n'
            + '\n'.join(f'  - {error}' for error in errors)
        )
