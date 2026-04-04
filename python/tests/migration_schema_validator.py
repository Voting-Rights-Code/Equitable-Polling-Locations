"""Symbolic schema state tracker for validating Alembic migration chains.

Walks the migration chain in revision order, tracks table/column/view state,
and flags any operation that references a nonexistent schema object.
No database required — pure Python AST and regex parsing.
"""
import ast
import os
import re


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
                f'[{migration_id}] create_table: {table_name} already exists'
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
                f'[{migration_id}] drop_table: {table_name} does not exist'
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
                f'[{migration_id}] add_column: table {table_name} '
                f'does not exist'
            )
            return
        if column_name in self.tables[table_name]:
            self.errors.append(
                f'[{migration_id}] add_column: column {column_name} '
                f'already exists in {table_name}'
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
                f'[{migration_id}] drop_column: table {table_name} '
                f'does not exist'
            )
            return
        if column_name not in self.tables[table_name]:
            self.errors.append(
                f'[{migration_id}] drop_column: column {column_name} '
                f'does not exist in {table_name}'
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
                f'[{migration_id}] alter_column: table {table_name} '
                f'does not exist'
            )
            return
        if column_name not in self.tables[table_name]:
            self.errors.append(
                f'[{migration_id}] alter_column: column {column_name} '
                f'does not exist in {table_name}'
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
                f'[{migration_id}] rename_table: {old_name} '
                f'does not exist'
            )
            return
        if new_name in self.tables:
            self.errors.append(
                f'[{migration_id}] rename_table: {new_name} '
                f'already exists'
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
                f'[{migration_id}] rename_column: table {table_name} '
                f'does not exist'
            )
            return
        if old_column not in self.tables[table_name]:
            self.errors.append(
                f'[{migration_id}] rename_column: column {old_column} '
                f'does not exist in {table_name}'
            )
            return
        if new_column in self.tables[table_name]:
            self.errors.append(
                f'[{migration_id}] rename_column: column {new_column} '
                f'already exists in {table_name}'
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
                f'[{migration_id}] drop_view: view {view_name} '
                f'does not exist'
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


def extract_operations(source: str) -> list[dict]:
    """Extract schema operations from a migration file's upgrade() function.

    Parses the source using Python's ast module to find Alembic operations
    (create_table, add_column, etc.) and raw SQL execute calls containing
    RENAME TABLE/COLUMN statements.

    Args:
        source: Python source code of the migration file.

    Returns:
        List of operation dicts. Each dict has a 'type' key and operation-specific
        keys (e.g., 'table', 'column', 'old_name', 'new_name').
    """
    tree = ast.parse(source)
    upgrade_func = _find_upgrade_function(tree)
    if upgrade_func is None:
        return []

    operations = []
    for node in ast.walk(upgrade_func):
        if not isinstance(node, ast.Call):
            continue

        func_name = _get_call_name(node)
        if func_name == 'op.create_table':
            _parse_create_table(node, operations)
        elif func_name == 'op.drop_table':
            _parse_drop_table(node, operations)
        elif func_name == 'op.add_column':
            _parse_add_column(node, operations)
        elif func_name == 'op.drop_column':
            _parse_drop_column(node, operations)
        elif func_name == 'op.alter_column':
            _parse_alter_column(node, operations)
        elif func_name == 'op.execute':
            _parse_execute(node, operations)
        elif func_name == 'op.create_view':
            _parse_create_view(node, upgrade_func, operations)
        elif func_name == 'op.drop_view':
            _parse_drop_view(node, upgrade_func, operations)

    return operations


def _find_upgrade_function(tree: ast.Module) -> ast.FunctionDef | None:
    """Find the upgrade() function definition in the AST.

    Args:
        tree: Parsed AST of the migration module.

    Returns:
        The FunctionDef node for upgrade(), or None if not found.
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'upgrade':
            return node
    return None


def _get_call_name(node: ast.Call) -> str | None:
    """Extract the dotted name of a function call (e.g., 'op.create_table').

    Args:
        node: AST Call node.

    Returns:
        Dotted name string, or None if the call pattern is unrecognized.
    """
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f'{func.value.id}.{func.attr}'
    return None


def _get_string_arg(node: ast.Call, index: int) -> str | None:
    """Extract a string constant from a positional argument.

    Args:
        node: AST Call node.
        index: Positional argument index.

    Returns:
        The string value, or None if not a string constant.
    """
    if index >= len(node.args):
        return None
    arg = node.args[index]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _parse_create_table(node: ast.Call, operations: list[dict]) -> None:
    """Parse op.create_table() and extract table name and column names.

    Args:
        node: AST Call node for op.create_table().
        operations: List to append the parsed operation to.
    """
    table_name = _get_string_arg(node, 0)
    if table_name is None:
        return

    columns = set()
    for arg in node.args[1:]:
        if not isinstance(arg, ast.Call):
            continue
        call_name = _get_call_name(arg)
        if call_name == 'sa.Column':
            col_name = _get_string_arg(arg, 0)
            if col_name is not None:
                columns.add(col_name)

    operations.append({
        'type': 'create_table',
        'table': table_name,
        'columns': columns,
    })


def _parse_drop_table(node: ast.Call, operations: list[dict]) -> None:
    """Parse op.drop_table() and extract table name.

    Args:
        node: AST Call node for op.drop_table().
        operations: List to append the parsed operation to.
    """
    table_name = _get_string_arg(node, 0)
    if table_name is not None:
        operations.append({'type': 'drop_table', 'table': table_name})


def _parse_add_column(node: ast.Call, operations: list[dict]) -> None:
    """Parse op.add_column() and extract table and column names.

    Args:
        node: AST Call node for op.add_column().
        operations: List to append the parsed operation to.
    """
    table_name = _get_string_arg(node, 0)
    if table_name is None or len(node.args) < 2:
        return

    column_call = node.args[1]
    if isinstance(column_call, ast.Call):
        col_name = _get_string_arg(column_call, 0)
        if col_name is not None:
            operations.append({
                'type': 'add_column',
                'table': table_name,
                'column': col_name,
            })


def _parse_drop_column(node: ast.Call, operations: list[dict]) -> None:
    """Parse op.drop_column() and extract table and column names.

    Args:
        node: AST Call node for op.drop_column().
        operations: List to append the parsed operation to.
    """
    table_name = _get_string_arg(node, 0)
    column_name = _get_string_arg(node, 1)
    if table_name is not None and column_name is not None:
        operations.append({
            'type': 'drop_column',
            'table': table_name,
            'column': column_name,
        })


def _parse_alter_column(node: ast.Call, operations: list[dict]) -> None:
    """Parse op.alter_column() and extract table and column names.

    Args:
        node: AST Call node for op.alter_column().
        operations: List to append the parsed operation to.
    """
    table_name = _get_string_arg(node, 0)
    column_name = _get_string_arg(node, 1)
    if table_name is not None and column_name is not None:
        operations.append({
            'type': 'alter_column',
            'table': table_name,
            'column': column_name,
        })


def _reconstruct_sql_from_ast(node: ast.expr) -> str | None:
    """Reconstruct a SQL string from an AST node, replacing f-string
    expressions with a wildcard placeholder.

    Handles:
    - String constants: returned as-is
    - F-strings (JoinedStr): expressions replaced with '*'
    - sa.text() wrappers: unwrapped to get inner string
    - Implicit string concatenation: handled by Python's AST parser

    Args:
        node: AST expression node containing the SQL string.

    Returns:
        Reconstructed SQL string with placeholders, or None if unparseable.
    """
    # Unwrap sa.text() wrapper
    if isinstance(node, ast.Call):
        call_name = _get_call_name(node)
        if call_name == 'sa.text' and node.args:
            return _reconstruct_sql_from_ast(node.args[0])
        return None

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append('*')
            else:
                parts.append('*')
        return ''.join(parts)

    return None


# Regex patterns for BigQuery ALTER TABLE statements.
# The \s* between backtick and RENAME handles the missing-space bug
# where implicit f-string concatenation omits the space.
_RENAME_TABLE_PATTERN = re.compile(
    r'ALTER\s+TABLE\s+`[^`]*\.(\w+)`\s*RENAME\s+TO\s+`(\w+)`',
    re.IGNORECASE
)

_RENAME_COLUMN_PATTERN = re.compile(
    r'ALTER\s+TABLE\s+`[^`]*\.(\w+)`\s*RENAME\s+COLUMN\s+`(\w+)`\s+TO\s+`(\w+)`',
    re.IGNORECASE
)


def _parse_execute(node: ast.Call, operations: list[dict]) -> None:
    """Parse op.execute() calls for ALTER TABLE RENAME statements.

    Reconstructs the SQL string from the AST (handling f-strings and
    sa.text wrappers) and uses regex to extract rename operations.

    Args:
        node: AST Call node for op.execute().
        operations: List to append parsed operations to.
    """
    if not node.args:
        return

    sql = _reconstruct_sql_from_ast(node.args[0])
    if sql is None:
        return

    # Check for RENAME COLUMN first (more specific pattern)
    rename_col_match = _RENAME_COLUMN_PATTERN.search(sql)
    if rename_col_match:
        operations.append({
            'type': 'rename_column',
            'table': rename_col_match.group(1),
            'old_column': rename_col_match.group(2),
            'new_column': rename_col_match.group(3),
        })
        return

    # Check for RENAME TABLE
    rename_table_match = _RENAME_TABLE_PATTERN.search(sql)
    if rename_table_match:
        operations.append({
            'type': 'rename_table',
            'old_name': rename_table_match.group(1),
            'new_name': rename_table_match.group(2),
        })


def _parse_create_view(node: ast.Call, upgrade_func: ast.FunctionDef,
                       operations: list[dict]) -> None:
    """Parse op.create_view() and extract the view name.

    Args:
        node: AST Call node for op.create_view().
        upgrade_func: The upgrade() function AST node (for variable lookup).
        operations: List to append parsed operations to.
    """
    view_name = _extract_view_name(node.args[0] if node.args else None,
                                   upgrade_func)
    if view_name is not None:
        operations.append({'type': 'create_view', 'view': view_name})


def _parse_drop_view(node: ast.Call, upgrade_func: ast.FunctionDef,
                     operations: list[dict]) -> None:
    """Parse op.drop_view() and extract the view name.

    Args:
        node: AST Call node for op.drop_view().
        upgrade_func: The upgrade() function AST node (for variable lookup).
        operations: List to append parsed operations to.
    """
    view_name = _extract_view_name(node.args[0] if node.args else None,
                                   upgrade_func)
    if view_name is not None:
        operations.append({'type': 'drop_view', 'view': view_name})


def _extract_view_name(arg_node: ast.expr | None,
                       upgrade_func: ast.FunctionDef) -> str | None:
    """Extract a view name from a create_view/drop_view argument.

    Handles two patterns:
    1. Direct call: op.create_view(build_<name>(db_dataset))
    2. Variable: op.create_view(var_name) where var_name = build_<name>(...)

    Args:
        arg_node: The argument AST node passed to create_view/drop_view.
        upgrade_func: The upgrade() function for variable resolution.

    Returns:
        The view name, or None if it cannot be determined.
    """
    if arg_node is None:
        return None

    # Pattern 1: direct call — op.create_view(build_something(db_dataset))
    if isinstance(arg_node, ast.Call):
        return _view_name_from_builder_call(arg_node)

    # Pattern 2: variable — op.create_view(var)
    if isinstance(arg_node, ast.Name):
        var_name = arg_node.id
        for stmt in ast.walk(upgrade_func):
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == var_name
                    and isinstance(stmt.value, ast.Call)):
                return _view_name_from_builder_call(stmt.value)

    return None


def _view_name_from_builder_call(call_node: ast.Call) -> str | None:
    """Extract a view name from a build_<name>() function call.

    Args:
        call_node: AST Call node for the builder function.

    Returns:
        The view name (portion after 'build_'), or None.
    """
    if isinstance(call_node.func, ast.Name):
        func_name = call_node.func.id
        if func_name.startswith('build_'):
            return func_name[len('build_'):]
    return None
