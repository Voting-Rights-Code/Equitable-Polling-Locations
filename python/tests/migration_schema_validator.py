"""Symbolic schema state tracker for validating Alembic migration chains.

Walks the migration chain in revision order, tracks table/column/view state,
and flags any operation that references a nonexistent schema object.
No database required — pure Python AST and regex parsing.
"""
import ast
import os


class SchemaState:
    """Tracks tables, columns, and views through a migration chain.

    Records errors when operations reference nonexistent schema objects
    (e.g., renaming a column that doesn't exist at that point in the chain).
    """

    def __init__(self):
        self.tables: dict[str, set[str]] = {}
        self.views: set[str] = set()
        self.errors: list[str] = []

    def create_table(self, table_name: str, columns: set[str],
                     migration_id: str) -> None:
        """Register a new table with its columns.

        Args:
            table_name: Name of the table to create.
            columns: Set of column names in the table.
            migration_id: Alembic revision ID for error reporting.
        """
        if table_name in self.tables:
            self.errors.append(
                f"[{migration_id}] create_table: '{table_name}' already exists"
            )
            return
        self.tables[table_name] = set(columns)

    def drop_table(self, table_name: str, migration_id: str) -> None:
        """Remove a table from tracked state.

        Args:
            table_name: Name of the table to drop.
            migration_id: Alembic revision ID for error reporting.
        """
        if table_name not in self.tables:
            self.errors.append(
                f"[{migration_id}] drop_table: '{table_name}' does not exist"
            )
            return
        del self.tables[table_name]

    def add_column(self, table_name: str, column_name: str,
                   migration_id: str) -> None:
        """Add a column to an existing table.

        Args:
            table_name: Table to add the column to.
            column_name: Name of the new column.
            migration_id: Alembic revision ID for error reporting.
        """
        if table_name not in self.tables:
            self.errors.append(
                f"[{migration_id}] add_column: table '{table_name}' "
                f"does not exist"
            )
            return
        if column_name in self.tables[table_name]:
            self.errors.append(
                f"[{migration_id}] add_column: column '{column_name}' "
                f"already exists in '{table_name}'"
            )
            return
        self.tables[table_name].add(column_name)

    def drop_column(self, table_name: str, column_name: str,
                    migration_id: str) -> None:
        """Remove a column from an existing table.

        Args:
            table_name: Table to remove the column from.
            column_name: Name of the column to remove.
            migration_id: Alembic revision ID for error reporting.
        """
        if table_name not in self.tables:
            self.errors.append(
                f"[{migration_id}] drop_column: table '{table_name}' "
                f"does not exist"
            )
            return
        if column_name not in self.tables[table_name]:
            self.errors.append(
                f"[{migration_id}] drop_column: column '{column_name}' "
                f"does not exist in '{table_name}'"
            )
            return
        self.tables[table_name].discard(column_name)

    def alter_column(self, table_name: str, column_name: str,
                     migration_id: str) -> None:
        """Verify a column exists for alteration (e.g., nullable change).

        Args:
            table_name: Table containing the column.
            column_name: Column being altered.
            migration_id: Alembic revision ID for error reporting.
        """
        if table_name not in self.tables:
            self.errors.append(
                f"[{migration_id}] alter_column: table '{table_name}' "
                f"does not exist"
            )
            return
        if column_name not in self.tables[table_name]:
            self.errors.append(
                f"[{migration_id}] alter_column: column '{column_name}' "
                f"does not exist in '{table_name}'"
            )

    def rename_table(self, old_name: str, new_name: str,
                     migration_id: str) -> None:
        """Rename a table, preserving its columns.

        Args:
            old_name: Current table name.
            new_name: New table name.
            migration_id: Alembic revision ID for error reporting.
        """
        if old_name not in self.tables:
            self.errors.append(
                f"[{migration_id}] rename_table: '{old_name}' "
                f"does not exist"
            )
            return
        if new_name in self.tables:
            self.errors.append(
                f"[{migration_id}] rename_table: '{new_name}' "
                f"already exists"
            )
            return
        self.tables[new_name] = self.tables.pop(old_name)

    def rename_column(self, table_name: str, old_column: str,
                      new_column: str, migration_id: str) -> None:
        """Rename a column within a table.

        Args:
            table_name: Table containing the column.
            old_column: Current column name.
            new_column: New column name.
            migration_id: Alembic revision ID for error reporting.
        """
        if table_name not in self.tables:
            self.errors.append(
                f"[{migration_id}] rename_column: table '{table_name}' "
                f"does not exist"
            )
            return
        if old_column not in self.tables[table_name]:
            self.errors.append(
                f"[{migration_id}] rename_column: column '{old_column}' "
                f"does not exist in '{table_name}'"
            )
            return
        if new_column in self.tables[table_name]:
            self.errors.append(
                f"[{migration_id}] rename_column: column '{new_column}' "
                f"already exists in '{table_name}'"
            )
            return
        self.tables[table_name].discard(old_column)
        self.tables[table_name].add(new_column)

    def create_view(self, view_name: str,
                    migration_id: str) -> None:  # pylint: disable=unused-argument
        """Register a new view.

        Args:
            view_name: Name of the view to create.
            migration_id: Alembic revision ID for error reporting.
                Accepted for API consistency; not used because duplicate
                view creation is not treated as an error.
        """
        self.views.add(view_name)

    def drop_view(self, view_name: str, migration_id: str) -> None:
        """Remove a view from tracked state.

        Args:
            view_name: Name of the view to drop.
            migration_id: Alembic revision ID for error reporting.
        """
        if view_name not in self.views:
            self.errors.append(
                f"[{migration_id}] drop_view: view '{view_name}' "
                f"does not exist"
            )
            return
        self.views.discard(view_name)


def get_revision_info(file_path: str) -> dict:
    """Extract revision metadata from an Alembic migration file.

    Parses the module-level assignments for 'revision' and 'down_revision'.

    Args:
        file_path: Path to the migration .py file.

    Returns:
        Dict with keys: 'revision', 'down_revision', 'file_path'.
    """
    with open(file_path, encoding='utf-8') as source_file:
        tree = ast.parse(source_file.read())

    revision = None
    down_revision = None

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        if isinstance(node, ast.AnnAssign):
            target_name = (
                node.target.id if isinstance(node.target, ast.Name) else None
            )
            value_node = node.value
        else:
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            target_name = target.id if isinstance(target, ast.Name) else None
            value_node = node.value

        if target_name == 'revision':
            revision = _extract_constant(value_node)
        elif target_name == 'down_revision':
            down_revision = _extract_constant(value_node)

    return {
        'revision': revision,
        'down_revision': down_revision,
        'file_path': file_path,
    }


def _extract_constant(node: ast.expr):
    """Extract a constant value from an AST node.

    Handles Constant nodes (strings, None) directly.
    Returns None for non-constant expressions.

    Args:
        node: AST expression node.

    Returns:
        The constant value, or None if not extractable.
    """
    if isinstance(node, ast.Constant):
        return node.value
    return None


def build_migration_chain(versions_dir: str) -> list[dict]:
    """Build an ordered list of migrations from the revision chain.

    Reads all .py files in the versions directory, extracts their revision
    metadata, and orders them by following the down_revision links from
    the initial migration (down_revision=None) to the head.

    Args:
        versions_dir: Path to the Alembic versions directory.

    Returns:
        List of revision info dicts in chain order (oldest first).

    Raises:
        ValueError: If no initial migration found or chain is broken.
    """
    migration_files = [
        os.path.join(versions_dir, filename)
        for filename in os.listdir(versions_dir)
        if filename.endswith('.py')
    ]

    all_revisions = [get_revision_info(path) for path in migration_files]

    # Find the initial migration (down_revision is None)
    initial = [rev for rev in all_revisions if rev['down_revision'] is None]
    if len(initial) != 1:
        raise ValueError(
            f'Expected exactly 1 initial migration, found {len(initial)}'
        )

    chain = [initial[0]]
    visited = {initial[0]['revision']}

    # Build a reverse lookup: down_revision -> revision
    next_lookup = {}
    for rev in all_revisions:
        if rev['down_revision'] is not None:
            next_lookup[rev['down_revision']] = rev

    current = initial[0]
    while current['revision'] in next_lookup:
        current = next_lookup[current['revision']]
        if current['revision'] in visited:
            raise ValueError(
                f'Cycle detected at revision {current["revision"]}'
            )
        visited.add(current['revision'])
        chain.append(current)

    return chain
