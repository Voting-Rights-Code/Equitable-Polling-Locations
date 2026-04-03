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

## Documentation Strategy

This is an open source project. Keep the repo authoritative:

- **Finalized decisions** → `docs/decisions/` (ADR format: "Why we chose X over Y")
- **Specs and plans** → add to the originating issue/ticket, not as separate issues
- **Do NOT commit** rough specs, exploratory plans, or in-progress design docs to the repo
- Outside contributors treat anything in `main` as gospel — keep it clean

## R Analysis Toolkit (`R/`)

Post-optimization result analysis and visualization scripts. See `R/CLAUDE.md` for conventions.

## Backend API (`python/`)

Python solver and API. See `python/CLAUDE.md` for conventions.
