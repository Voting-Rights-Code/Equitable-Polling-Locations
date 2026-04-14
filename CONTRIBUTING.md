# Contributing to Equitable Polling Locations

Welcome to Voting Rights Code! Thank you for considering contributing to this project. Whether you're fixing a bug, adding a feature, or improving documentation, your work helps ensure fair access to polling places for voters across communities.

**Equitable Polling Locations** is a Python optimization tool that selects equitable polling locations using the Kolm-Pollak (KP) distance metric. KP minimizes mean voter travel distance while penalizing inequality — higher sensitivity values weight equity more heavily. The model runs in Docker (Linux/amd64).

**Quick start:**

1. Read this guide (especially [Getting Started](#getting-started) and [Code Style](#code-style))
2. [Set up your development environment](#development-environment)
3. Pick an issue or propose a change
4. [Submit a pull request](#submitting-changes)

Questions? [Ask us on Discord](https://discord.com/channels/1106301559811350540/1106301560507609241).

## Code of Conduct

**Who we are:** A bunch of volunteers that care enough about civil rights to check our egos at the door and roll up our sleeves.

- We don't have a ton of processes (yet) because we're still figuring it out
- We do have good communication skills and ask for help when we need it, and get it
- We treat each other like friends even if we don't agree with everyone's every last idea
- Care enough about the work to get it right, not just the 80% solution
- Care enough about ourselves and each other to not force ourselves and each other to do work we don't want to do

### How we work

1. **Communicate.** We can't fix a problem if we don't know it needs fixing. Everyone is responsible for the quality and good this project does. If we don't see something we need:
    1. Ask us why this is so (there may or may not be a good reason)
    2. Build it

2. **Code review early. Code review often.** Do not merge without a code review.
    1. As we start a feature branch, check in with the team to see what unwritten requirements exist
    2. Follow good coding practices, including commenting code, implementing tests, delinting code
    3. Do not merge into main until it is polished code
        - This may require asking for code reviews on feature branches for larger features
        - **If polishing a feature for merging is not what you're up for, that's okay. Tag it, and someone will get to it eventually.**
    4. All pull requests will be reviewed by at least two maintainers before merge

3. **Respect our own and each other's time.**
    1. Don't go too far into a project without checking in
        - If you don't understand how someone else is working on a part of the problem, ask them
        - If you don't know who else is working on a relevant part of the project, ask
        - When you need support on a project, schedule time on someone else's calendar
        - When someone asks for time and help, respond promptly and be realistic about what support you can provide
    2. Avoid burnout
        - Be realistic about your own schedule and time commitment
        - Take on tasks that bring you joy
            - **If a task doesn't bring you joy, don't do it.** Document that it needs doing and move on. Someone else will get to it.

4. **If we make a mistake, or think someone else has made a mistake, talk about it.**


## Table of Contents

<!-- toc -->

- [Getting Started](#getting-started)
- [Codebase Structure](#codebase-structure)
- [Development Environment](#development-environment)
- [Code Style](#code-style)
  - [Python](#python)
  - [R](#r)
  - [Commit Messages](#commit-messages)
- [Testing](#testing)
  - [Unit Tests](#unit-tests)
  - [End-to-End (E2E) Tests](#end-to-end-e2e-tests)
  - [Test-Driven Development](#test-driven-development)
- [Linting](#linting)
- [Submitting Changes](#submitting-changes)
  - [Branching](#branching)
  - [Pull Requests](#pull-requests)
  - [Code Review](#code-review)
  - [Merging](#merging)
- [Writing Documentation](#writing-documentation)
- [AI-Assisted Development](#ai-assisted-development)
  - [Claude Code](#claude-code)
  - [GitHub MCP Server](#github-mcp-server)
  - [Plugins](#plugins)
- [Getting Help](#getting-help)

<!-- tocstop -->


## Getting Started

Before contributing, you'll need a few tools installed.

### Docker (required)

1. Install [Docker Desktop](https://www.docker.com/).
2. Allocate at least **8 GB of RAM** to Docker:
    - **macOS:** Docker Desktop → Settings → Resources → Memory
    - **Windows (WSL):** Set memory in `.wslconfig` in your `%USERPROFILE%` directory

### Git LFS

This repository uses [Git LFS](https://git-lfs.com/) for large data files.

1. Download and install Git LFS from [git-lfs.com](https://git-lfs.com/)
    - On Linux/macOS, if the standard install doesn't work, try `sudo ./install.sh` after downloading
2. Run `git lfs install` once before cloning
3. Clone the repository

### Configuration

1. Copy `settings_example.yaml` to `settings.yaml` in the project root
2. The settings file configures different environments (dev, prod, test) and their database connections
3. Additional environments may be configured as necessary

### Verify Your Installation

From the project root, run:

```bash
docker compose run --rm app pytest
```

All tests should pass. See [Installation](docs/to_install.md) for full setup details.


## Codebase Structure

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
R/            # Post-optimization result analysis and visualization (see R/CLAUDE.md)
```

The `run.py` wrapper translates commands into Docker calls:

```
run.py <script_name> [args]  →  docker compose run --rm app python -m python.scripts.<script_name> [args]
```

See [Running the Program](docs/to_run.md) for full usage details and examples.


## Development Environment

### Docker (recommended)

Docker is the primary development method. All commands go through `run.py`, which handles Python dependencies, SCIP optimizer setup, and environment configuration inside the container.

```bash
# Run the model locally
python run.py model_run_cli -c NUM -l ./datasets/configs/<County>/config.yaml

# Run tests
docker compose run --rm app pytest

# Run E2E tests
python run.py e2e_tests
```

### Local Development with Conda (optional)

Conda can be set up for local development without Docker. This is useful for IDE integration and debugging.

1. Install conda if you do not have it already
    - This project uses SCIP as an optimizer, which is easily installed using conda but not using pip
    - If you do not have conda installed already, use the relevant instructions [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html)
2. Create and activate the conda environment (on Windows, use Anaconda Prompt):
    ```bash
    conda env create -f environment.yml
    conda activate equitable-polls
    ```

### Database Setup (optional)

Database-backed workflows require GCP credentials and a configured environment in `settings.yaml`.

- Run `gcloud auth application-default login` to set up Application Default Credentials
- The `run.py` wrapper mounts GCP credentials into the Docker container automatically
- Use **scratch datasets** for development and testing — never develop directly against production
- Run `alembic upgrade head` to initialize or update the database schema

See [Database](docs/database.md) for full documentation on schema, imports, scratch dataset setup, and Alembic migrations.


## Code Style

### Python

This project follows the [Google Python style guide](https://google.github.io/styleguide/pyguide.html), enforced via Pylint (see `.pylintrc`).

- **Indentation:** 4 spaces
- **Line length:** 120 characters maximum
- **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for constants
- **Readability over brevity:** Spell out variable names (`polling_location` not `pl`, `equity_score` not `eq_s`). Short names are acceptable only for loop counters and lambdas.

#### Docstrings

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

#### Comments

Inline comments should explain *why*, not restate *what* the code does. Keep them concise and follow PEP 8 (single space after `#`, sentence case).

### R

The R analysis scripts in `R/` follow the [tidyverse style guide](https://style.tidyverse.org/).

- **Naming:** `snake_case` for all names. Files: `snake_case.R`
- **Assignment:** Always `<-`, never `=`. Use `TRUE`/`FALSE`, never `T`/`F`
- **Data manipulation:** This project uses `data.table` — use `dt[i, j, by]` idiom, not dplyr verbs. Do not mix.
- **Vectorize operations:** Avoid explicit loops for element-wise work. Use `vapply()` over `sapply()`. Use `seq_along(x)` / `seq_len(n)`, never `1:length(x)`.
- **Linting:** Lint with `lintr::lint()`. Format with `styler::style_file()`.

### Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description
```

- **Types:** `feat`, `fix`, `refactor`, `test`, `chore`, `docs`
- **Scope:** Module name — `solver`, `database`, `scripts`, etc.

Examples:
```
feat(solver): add overcrowding constraint support
fix(database): handle null driving distances in import
test(e2e): add CSV workflow end-to-end tests
docs(contributing): consolidate contributing guide
```


## Testing

### Unit Tests

Unit tests live in `python/tests/` and cover the solver, model data, config loading, and utilities. Run them via Docker:

```bash
docker compose run --rm app pytest
```

Or locally with a conda environment:

```bash
pytest
```

### End-to-End (E2E) Tests

E2E tests exercise the full CLI scripts via subprocess, verifying that each command produces correct output files and database records. They live in `python/tests/e2e/`.

Test data is automatically templated from `datasets/polling/testing/` with a unique session ID per run, so multiple test runs (even concurrent ones) will not interfere with each other.

There are two categories of E2E tests:

- **CSV tests (`e2e_csv`)** — Test CSV-based workflows (`model_run_cli`, `auto_generate_config`). These always run and require no external dependencies.
- **DB tests (`e2e_db`)** — Test database-backed workflows (`db_import_*_cli`, `model_run_db_cli`). These require a `test` environment configured in `settings.yaml` and valid GCP credentials. They skip gracefully when either is unavailable.

#### Running E2E Tests

Via Docker (recommended):

```bash
# All E2E tests
python run.py e2e_tests

# CSV tests only (no DB or GCP credentials required)
python run.py e2e_tests -m e2e_csv

# DB tests only (requires 'test' environment in settings.yaml + GCP credentials)
python run.py e2e_tests -m e2e_db

# Run a specific test file
python run.py e2e_tests python/tests/e2e/test_model_run_cli.py

# Verbose output
python run.py e2e_tests -v
```

Or locally with a conda environment:

```bash
pytest python/tests/e2e/
pytest python/tests/e2e/ -m e2e_csv
```

#### Setting Up DB Tests

To run the DB E2E tests:

1. Ensure `settings.yaml` has a `test` environment configured (see `settings_example.yaml`)
2. Ensure GCP Application Default Credentials are set up (`gcloud auth application-default login`)
3. Run via `python run.py e2e_tests -m e2e_db` — the `run.py` wrapper mounts GCP credentials into the Docker container automatically

DB tests clean up after themselves by deleting all `e2e_`-prefixed data from the test dataset at both the start and end of each session.

### Test-Driven Development

All code should be written using TDD:

1. **Write a failing test first** — before writing any implementation code, write a test that captures the desired behavior and confirm it fails for the right reason.
2. **Write the minimum code to pass** — implement only enough to make the test green; do not add logic that is not covered by a test.
3. **Refactor** — clean up while keeping all tests green.

When modifying existing code, update the associated tests before or alongside the change, and confirm all relevant tests pass before considering the work done.

### Pre-Merge Checklist

Before merging any change, run:

```bash
python run.py test
pylint python/
```

All tests and lints must pass.


## Linting

### Python

All code changes must pass Pylint before committing:

```bash
pylint python/
```

- **Warnings are errors** — fix all Pylint warnings. Do not add `# pylint: disable` without a comment explaining why the suppression is necessary.
- Run pytest with `-W error` to catch Python warnings as test failures.

### R

```bash
# In R console
lintr::lint("path/to/file.R")
styler::style_file("path/to/file.R")
```


## Submitting Changes

### Branching

Create a feature branch from `main` for your work. Check in with the team early to surface any unwritten requirements or overlapping work.

### Pull Requests

When your change is ready:

1. Ensure all tests pass (`python run.py test`)
2. Ensure lint passes (`pylint python/`)
3. Include tests for new features
4. Write a clear PR description explaining what changed and why

### Code Review

All pull requests require review by at least **two maintainers** before merge.

- Request reviews early for larger features — don't wait until the entire feature is complete
- If polishing a feature for merging is not what you're up for, that's okay. Tag it, and someone will get to it eventually
- Reviewers: respond promptly and be realistic about what support you can provide

### Merging

- Do not merge into `main` until the code is polished
- All tests and lint must pass
- Larger features may require intermediate code reviews on feature branches before the final merge


## Writing Documentation

This is an open source project. Outside contributors treat anything in `main` as gospel — keep the repo authoritative.

- **Finalized decisions** go in `docs/development/decisions/` using ADR format ("Why we chose X over Y")
- **Specs and plans** go on the originating issue or ticket, not as separate files in the repo
- **Do NOT commit** rough specs, exploratory plans, or in-progress design docs to the repo


## AI-Assisted Development

### Claude Code

Install Claude Code following the official instructions at [claude.ai/download](https://claude.ai/download).

### GitHub MCP Server

Claude Code uses the GitHub MCP server to create and manage issues and pull requests. To set it up:

1. **Generate a fine-grained personal access token:**
    1. Go to [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta)
    2. Click **Generate new token**
    3. Under **Repository access**, select **Only select repositories** and choose `Voting-Rights-Code/Equitable-Polling-Locations`
    4. Under **Permissions → Repository permissions**, grant:
        - **Issues** — Read and write
        - **Pull requests** — Read and write
    5. Click **Generate token** and copy it

2. **Add the MCP server to Claude Code:**

    ```bash
    claude mcp add github -s user -e GITHUB_PERSONAL_ACCESS_TOKEN="<your-token>" -- npx -y @modelcontextprotocol/server-github
    ```

    Using `-s user` keeps the token out of the repo (stored in `~/.claude/.mcp.json`).

3. **Verify:** Restart Claude Code and run `/mcp`. The `github` server should show as connected.

### Plugins

Install the following plugins from `claude-plugins-official` via `/plugins`:

- **superpowers** — planning, code review, and development workflow skills
- **commit-commands** — commit, push, and PR shortcuts
- **pyright-lsp** — Python type checking and language server integration


## Getting Help

- **Discord:** [Ask us on Discord](https://discord.com/channels/1106301559811350540/1106301560507609241) — we'd love to talk to you, even if you're just browsing
- **Check in early:** If you're unsure who else is working on a relevant part of the project, ask. If you don't understand how someone else is approaching a problem, ask them.
- **We ask for help when we need it, and get it.** Don't hesitate to reach out.
