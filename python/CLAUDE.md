# Python Solver — Conventions

## Code Style

- Google Python style guide (`.pylintrc`)
- 4-space indentation, 120 char line limit
- `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` constants
- All code changes must pass `pylint python/` before committing

### Docstrings

All new functions, methods, and classes must include a Google-style docstring:

```python
def example(value: int) -> str:
    """One-line summary of what the function does.

    Args:
        value: Description of the parameter.

    Returns:
        Description of the return value.

    Raises:
        ValueError: When and why it is raised.
    """
```

When code is changed or refactored, update any affected docstrings to stay accurate.

### Comments

Inline comments should explain *why*, not restate *what* the code does. Keep them concise and follow PEP 8 (single space after `#`, sentence case).

## Test-Driven Development

All code must be written using TDD:

1. **Write a failing test first** — before writing any implementation code, write a test that captures the desired behaviour and confirm it fails for the right reason.
2. **Write the minimum code to pass** — implement only enough to make the test green; do not add logic that is not covered by a test.
3. **Refactor** — clean up while keeping all tests green.

When modifying existing code, update the associated tests before or alongside the change, and confirm all relevant tests pass before considering the work done.

## Key Conventions

- Config paths are case-sensitive: use `Gwinnett_GA`, not `Gwinnett_Ga`
- Two data sources: `csv` (local files) or `db` (BigQuery) — set in `PollingModelConfig`
- Environment names are defined in `settings.yaml`
- Git LFS required for large dataset files (distances, shapefiles)
- `datasets/configs/testing/*.yaml` test configs are committed despite the blanket `*.yaml` gitignore rule — use `git add -f` when adding a new one

## Contributing

- Include tests for new features
- Communicate early about work in progress
