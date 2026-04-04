"""Tests for migration schema validator."""
import os

from python.tests.migration_schema_validator import (
    SchemaState, get_revision_info, build_migration_chain,
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
