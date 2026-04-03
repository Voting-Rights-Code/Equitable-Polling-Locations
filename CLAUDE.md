# Equitable Polling Locations

Python optimization tool that selects equitable polling locations using the Kolm-Pollak (KP) distance metric. KP minimizes mean voter travel distance while penalizing inequality via a sensitivity parameter `beta` — higher beta values weight equity more heavily. Runs in Docker (Linux/amd64).

## Setup

- Requires Docker with ≥8GB RAM and `git-lfs`
- Copy `settings_example.yaml` → `settings.yaml` and configure environments
- GCP credentials required for DB-backed runs (mounted automatically via `run.py`)

See `docs/to_install.md` for full setup instructions.

## Rules

- **No compound shell commands** — never wrap commands in `cd && ...`, subshells `()`, redirects `2>&1`, or pipes `| grep`. Run simple commands directly (`python run.py test`); use Read/Grep tools to filter output.
- **No inline scripts** — never use Python/sed/awk heredoc scripts via Bash to edit code. Use the Edit tool. Let pylint find all sites, then fix each individually.
- **Warnings are errors** — fix all Pylint warnings before committing. Do not add `# pylint: disable` without a comment explaining why. Run pytest with `-W error`.
- **Readability over brevity** — spell out variable names (`polling_location` not `pl`, `equity_score` not `eq_s`). Short names only for loop counters and lambdas.
- **Conventional Commits** — format: `type(scope): description`. Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`. Scope: module name (`solver`, `database`, `scripts`).
- **Before merging** — run `python run.py test` and `pylint python/`. All tests and lints must pass.

## Commands

**Run the model (local files):**
```bash
python run.py model_run_cli -c NUM -l ./datasets/configs/<County>/config.yaml
python run.py model_run_db_cli -e ENV -c NUM -l config_set/config_name
```
Add `-vv` for verbose logging.

**Tests:**
```bash
docker compose run --rm app pytest
```

**E2E tests:**
```bash
# All e2e tests via Docker
python run.py e2e_tests

# CSV tests only (no DB required)
python run.py e2e_tests -m e2e_csv

# DB tests only (requires 'test' environment in settings.yaml + GCP credentials)
python run.py e2e_tests -m e2e_db

# Locally (conda env)
pytest python/tests/e2e/
```

**Lint:**
```bash
pylint python/
```

**Local dev (optional, requires conda):**
```bash
conda env create -f environment.yml
conda activate equitable-polls
```

See `docs/to_run.md` for full usage details.

## Architecture

```
python/
  solver/     # KP optimization core: config, data prep, penalties, solver, results
  scripts/    # CLI entry points (model_run_cli, model_run_db_cli, db_import_*, etc.)
  database/   # SQLAlchemy BigQuery ORM + Alembic migrations
  utils/      # Env handling, GCP credentials, directory constants
  tests/      # pytest suite; fixtures in conftest.py
    e2e/      # End-to-end CLI tests (subprocess-based, session-isolated)
run.py        # Docker wrapper; auto-discovers scripts in python/scripts/
datasets/     # Sample data by county: configs, polling locations, distances
```

`run.py <script_name> [args]` → `docker compose run --rm app python -m python.scripts.<script_name> [args]`

## R Analysis Toolkit (`R/`)

Post-optimization result analysis and visualization scripts. Secondary to the Python solver — used for analyzing and mapping optimization results.

| Directory | Purpose |
|-----------|---------|
| `R/result_analysis/` | Main analysis scripts (per-county configs) |
| `R/result_analysis/utility_functions/` | Shared functions: storage, graphs, maps, config loading |
| `R/result_analysis/deprecated/` | Archived historical analyses |
| `R/tests/` | Manual verification scripts (not automated) |

Key libraries: `data.table`, `ggplot2`, `sf`, `bigrquery`, `googleCloudStorageR`, `yaml`, `plotly`. No formal R package structure — standalone analysis scripts. No automated R test runner.

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

## Contributing

- PRs require 2 maintainer reviews; lint before merging
- Include tests for new features
- Communicate early about work in progress
