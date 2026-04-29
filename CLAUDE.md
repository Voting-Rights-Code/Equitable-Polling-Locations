# Equitable Polling Locations

Python optimization tool that selects equitable polling locations using the Kolm-Pollak (KP) distance metric. KP minimizes mean voter travel distance while penalizing inequality via a sensitivity parameter `beta` — higher beta values weight equity more heavily. Runs in Docker (Linux/amd64).

## Setup

- Requires Docker with ≥8GB RAM and `git-lfs`
- Copy `settings_example.yaml` → `settings.yaml` and configure environments
- GCP credentials required for DB-backed runs (mounted automatically via `run.py`)

See `docs/to_install.md` for full setup instructions.

## DevContainer

This project is designed to be developed inside the `.devcontainer/`. Full first-time setup instructions, volume layout, reset commands, and the Zed pre-build workaround are in `CONTRIBUTING.md` (sections: "Dev Container — VS Code or Zed" and "Git from inside the container"). Read those before opening the project for the first time.

## Rules

- **No compound shell commands** — never wrap commands in `cd && ...`, subshells `()`, redirects `2>&1`, or pipes `| grep`. Run simple commands directly (`python run.py test`); use Read/Grep tools to filter output.
- **No inline scripts** — never use Python/sed/awk heredoc scripts via Bash to edit code. Use the Edit tool. Let pylint find all sites, then fix each individually.
- **Warnings are errors** — fix all Pylint warnings before committing. Do not add `# pylint: disable` without a comment explaining why. Run pytest with `-W error`.
- **Readability over brevity** — spell out variable names (`polling_location` not `pl`, `equity_score` not `eq_s`). Short names only for loop counters and lambdas.
- **Conventional Commits** — format: `type(scope): description`. Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`. Scope: module name (`solver`, `database`, `scripts`).
- **Before merging** — run `python run.py test` and `pylint python/`. All tests and lints must pass.

## Commands

**Detect your runtime first.** Behavior differs by environment:

- **Inside the dev container** — the file `/.dockerenv` exists, and/or the working directory is `/workspaces/Equitable-Polling-Locations`. The conda env `equitable-polls` is already active on `PATH`, so `pytest`, `pylint`, and `python -m python.scripts.<name>` work directly. `run.py` also works inside the container — it detects `/.dockerenv` and executes commands without any Docker wrapper. Do NOT call `docker compose` directly from inside the container.
- **On the host (macOS/Linux/WSL with Docker running)** — use `run.py` (the canonical wrapper) or `docker compose -f .devcontainer/docker-compose.yml run --rm app ...` directly. The project has a single image used by both the dev container and host invocations.
- **On the host with a local conda env** — activate `equitable-polls` and run `pytest` / `pylint` directly.

**Run the model (local files):**
```bash
# Host (via Docker)
python run.py model_run_cli -c NUM -l ./datasets/configs/<County>/config.yaml
python run.py model_run_db_cli -e ENV -c NUM -l config_set/config_name

# Inside dev container
python -m python.scripts.model_run_cli -c NUM -l ./datasets/configs/<County>/config.yaml
python -m python.scripts.model_run_db_cli -e ENV -c NUM -l config_set/config_name
```
Add `-vv` for verbose logging.

**Tests:**
```bash
# Host (via Docker)
python run.py test                         # all unit + e2e tests
python run.py e2e_tests                    # e2e only
python run.py e2e_tests -m e2e_csv        # CSV only, no DB required
python run.py e2e_tests -m e2e_db         # DB only, needs settings.yaml + GCP creds

# Inside dev container (or host with local conda env)
pytest                                     # all unit + e2e tests
pytest python/tests/e2e/                   # e2e only
pytest python/tests/e2e/ -m e2e_csv        # CSV only
```

Append `--keep-e2e-outputs` to any e2e command to retain session outputs under `datasets/{polling,driving,configs,results}/e2e_*` for manual inspection (gitignored). Cleanup: `rm -rf datasets/polling/e2e_* datasets/driving/e2e_* datasets/configs/e2e_* datasets/results/e2e_*_results`. See "Inspecting E2E Outputs" in CONTRIBUTING.md for full details.

**Lint:**
```bash
# Host (via Docker)
python run.py lint

# Inside dev container (or host with local conda env)
pylint python/
```

**R environment smoke test:**
```bash
# Host (via Docker)
python run.py r_test

# Inside dev container
Rscript R/tests/r_smoke_test.R
```
R is installed in the project image (see `.devcontainer/Dockerfile`). R package versions are pinned in `renv.lock` (the single source of truth, equivalent to `environment.yml` for Python). To add a new R package, use `install_r_packages.R` interactively, then regenerate `renv.lock` — see the workflow comments at the top of that script.

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
datasets/     # Data by county: configs, polling locations, distances
```

`run.py <script_name> [args]` → `docker compose -f .devcontainer/docker-compose.yml run --rm app python -m python.scripts.<script_name> [args]`

## Documentation Strategy

This is an open source project. Keep the repo authoritative:

- **Finalized decisions** → `docs/development/decisions/` (ADR format: "Why we chose X over Y")
- **Specs and plans** → add to the originating issue/ticket, not as separate issues
- **Do NOT commit** rough specs, exploratory plans, or in-progress design docs to the repo
- Outside contributors treat anything in `main` as gospel — keep it clean

## R Analysis Toolkit (`R/`)

Post-optimization result analysis and visualization scripts. See `R/CLAUDE.md` for conventions.

## Backend API (`python/`)

Python solver and API. See `python/CLAUDE.md` for conventions.
