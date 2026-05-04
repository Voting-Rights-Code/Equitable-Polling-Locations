# Contributing to Equitable Polling Locations

Welcome to Voting Rights Code! Thank you for considering contributing to this project. Whether you're fixing a bug, adding a feature, or improving documentation, your work helps ensure fair access to polling places for voters across communities.

**Equitable Polling Locations** is a Python optimization tool that selects equitable polling locations using the Kolm-Pollak (KP) distance metric. KP minimizes mean voter travel distance while penalizing inequality — higher sensitivity values weight equity more heavily. The model runs in Docker (Linux/amd64).

**Quick start:**

1. Read this guide (especially [Getting Started](#getting-started) and [Code Style](#code-style))
2. [Set up your development environment](#development-environment)
3. Pick an issue or propose a change
4. [Submit a pull request](#submitting-changes)

Questions? [Ask us on Discord](https://discord.com/channels/1106301559811350540/1106301560507609241).

## Table of Contents

<!-- toc -->

- [Getting Started](#getting-started)
- [Codebase Structure](#codebase-structure)
- [Development Environment](#development-environment)
  - [Docker (recommended)](#docker-recommended)
  - [Dev Container — VS Code or Zed (recommended for editor-integrated development)](#dev-container--vs-code-or-zed-recommended-for-editor-integrated-development)
  - [Local Development with Conda (optional)](#local-development-with-conda-optional)
  - [IDE Setup for Local Conda (optional)](#ide-setup-for-local-conda-optional)
  - [Database Setup (optional)](#database-setup-optional)
- [Code Style](#code-style)
  - [Python](#python)
  - [R](#r)
  - [Commit Messages](#commit-messages)
- [Testing](#testing)
  - [Unit Tests](#unit-tests)
  - [End-to-End (E2E) Tests](#end-to-end-e2e-tests)
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

Install one of the following container runtimes:

- **[Docker Desktop](https://www.docker.com/)** — works on macOS, Windows, and Linux
- **[OrbStack](https://orbstack.dev/)** (macOS only) — lighter weight and faster than Docker Desktop on Apple Silicon, with dynamic memory management

#### Memory configuration

The SCIP optimizer can use significant memory on larger counties (Tarrant County TX uses around 46 GB). Configure your runtime to allow at least **16 GB**, or **32 GB or more** if you plan to run large solves:

**Docker Desktop:**

Docker Desktop reserves a fixed amount of RAM regardless of actual usage.

- **macOS:** Docker Desktop → Settings → Resources → Memory → set to at least 16 GB (32 GB or more recommended)
- **Windows (WSL):** Create or edit `%USERPROFILE%\.wslconfig`:
    ```ini
    [wsl2]
    memory=32GB
    ```
    Then restart WSL: `wsl --shutdown`
- **Linux:** Docker Desktop → Settings → Resources → Memory. Alternatively, if running Docker Engine directly (no Desktop), memory is unlimited by default — no configuration needed.

**OrbStack (macOS):**

OrbStack shares your Mac's memory dynamically — it grows and shrinks on demand rather than reserving a fixed block. By default there is no hard cap, but OrbStack may conservatively limit the VM. To check or increase:

```bash
# Check current setting
orb config show

# Set an explicit limit (in MiB) — 32 GB example
orb config set memory_mib 32768
orb restart
```

Verify inside the container with `free -h`. If your Mac has 64 GB of RAM, allocating 48 GB to OrbStack still leaves plenty for macOS and your editor.

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
python run.py test
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
run.py <script_name> [args]  →  docker compose -f .devcontainer/docker-compose.yml run --rm app python -m python.scripts.<script_name> [args]
```

A single image powers both the dev container and the host-invoked `run.py` workflow, so editing `environment.yml` or `renv.lock` and rebuilding the image updates both paths at once.

See [Running the Program](docs/to_run.md) for full usage details and examples.


## Development Environment

### Docker (recommended)

Docker is the primary development method. All commands go through `run.py`, which handles Python dependencies, SCIP optimizer setup, and environment configuration inside the container.

```bash
# Run the model locally
python run.py model_run_cli -c NUM -l ./datasets/configs/<config_set>/<config_name>.yaml

# Run tests
python run.py test

# Run E2E tests
python run.py e2e_tests
```

The `-l` flag accepts a glob — e.g. `./datasets/configs/<config_set>/*.yaml` runs every config in the set.

### Dev Container — VS Code or Zed (recommended for editor-integrated development)

The project ships with a [dev container](https://containers.dev/) config in `.devcontainer/` that gives you a fully-configured Linux environment (conda env with all Python deps, pytest, pylint, Claude Code, Git LFS, native arm64 on Apple Silicon, native amd64 on Windows/Intel) without installing anything locally beyond Docker and your editor. The conda env inside the container is the same one defined by `environment.yml`, so tests and lint behave identically to the Docker and local-conda workflows.

**Prerequisites:**

- Docker (see above)
- Either:
    - **VS Code** with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
    - **Zed** (recent version with dev container support — see [Zed caveats](#zed-caveats) below)

**VS Code (recommended) — first open:**

1. Open the project folder in VS Code
2. When prompted "Folder contains a Dev Container configuration file", click **Reopen in Container** (or Command Palette → `Dev Containers: Reopen in Container`)
3. VS Code builds the image automatically on first open (~5-10 minutes; progress shown in the output panel). Rebuild happens only when `.devcontainer/Dockerfile` or `environment.yml` changes.
4. On first container creation, `postCreateCommand` installs R packages (~15-20 min, runs in the background). You can use the editor while it runs; R-dependent workflows just won't be available until it finishes. Subsequent opens are instant (packages persist in a docker volume).
5. Recommended extensions (Python, Pylint, Debugpy) install automatically inside the container
6. Open any file under `python/tests/` — **▶ Run Test** and **🐞 Debug Test** buttons appear inline above each test function. Test Explorer populates in the sidebar.

No manual commands required on macOS or Windows.

#### Windows contributors — notes

The dev container works on native Windows (Docker Desktop with WSL2 backend, which is the default) without WSL-side VS Code. A few Windows-specific details:

- **Line endings:** git on Windows defaults to `core.autocrlf=true`, which would otherwise make every file look modified inside the Linux container. The committed `.gitattributes` forces LF in the working tree on all platforms, so this is handled automatically for fresh clones. If you cloned before `.gitattributes` was committed, run once: `git add --renormalize . && git commit -m "chore: renormalize line endings"`.
- **Git auth:** no Windows-specific setup needed. Contributors who want to run `git push/pull` from inside the container use `gh auth login` once (see [Git from inside the container](#git-from-inside-the-container-optional)) — same flow as macOS and Linux.
- **GCP auth:** no Windows-specific setup needed. gcloud authentication happens inside the container (see [Database Setup](#database-setup-optional)) — container-local, so host path differences between `%APPDATA%\gcloud` and `~/.config/gcloud` don't matter.

**Git from inside the container (optional):**

If you want to run `git push/pull` inside the container (rather than from your host terminal), authenticate with GitHub once via device flow. The container doesn't mount your host SSH keys — `gh` provides git credentials instead.

In the container's integrated terminal:

```bash
gh auth login          # pick GitHub.com → HTTPS → "Login with a web browser"
gh auth setup-git      # configures git to use gh as its credential helper
```

`gh auth login` prints a URL and a short code; open the URL in your host browser, paste the code, approve, and come back. Your gh token is saved in the `gh-config` docker volume and persists across container rebuilds — no re-login needed unless you explicitly wipe the volume.

After `gh auth setup-git`, any clone URL (HTTPS or SSH) works for pull/push from inside the container. Alternatively, run git commands from your host terminal as usual — the project files are shared between host and container either way.

**SSH caveat under VS Code.** The Dev Containers extension forwards your host's SSH agent socket into shells it spawns — you'll see `SSH_AUTH_SOCK` set in VS Code terminals but not in the container's base env (`docker exec equitable_polling_locations-app-1 env` shows nothing). That means `git clone git@github.com:...` and other SSH operations also work under VS Code, using your host's in-memory keys. Under Zed there is no such forwarding. The exact socket path varies by VS Code version and host OS; the forwarding behavior is stable, the path isn't. The `gh` HTTPS credential helper is the canonical recommendation because it works in both editors and doesn't depend on the host having an SSH agent running.

#### Zed caveats

Zed's dev container pipeline has a bug where `build:` in `docker-compose.yml` is effectively ignored — it extracts only the Dockerfile's `FROM` line and skips every `RUN`/`COPY` step after it. As a result Zed cannot build this project's image directly. **Workaround: pre-build the image manually from your host terminal before opening in Zed:**

```bash
docker compose -f .devcontainer/docker-compose.build.yml build
```

Then open the project in Zed — it will start a container from the pre-built image. One-time setup per Zed contributor: Command Palette → search for `toolchain` → choose `/opt/conda/envs/equitable-polls/bin/python`. Zed's test runner needs this to find `pytest`. Additional pytest and pylint tasks are available via Command Palette → `task: spawn` (defined in `.zed/tasks.json`).

Rebuild the image (same command above) when `.devcontainer/Dockerfile` or `environment.yml` changes, then rebuild the container from Zed.

VS Code's dev container extension does not have this bug — VS Code users have no manual pre-build step.

**Verifying the container is ready:**

In the container's integrated terminal:

```bash
pytest --version       # should print: pytest 9.0.3
pylint --version       # should print: pylint 4.0.x
R --version            # should print: R version 4.3.x
claude --version       # should print a Claude Code version
ssh -T git@github.com  # should print: Hi <username>! You've successfully authenticated...
```

For R, also run the packages smoke test — but note that the R package install may still be running in the background on first open (see next subsection):

```bash
Rscript R/tests/r_smoke_test.R
```

**R: first-time setup**

R is configured automatically as part of the Dev Container flow — no manual setup steps beyond opening the project. Here's what happens and how to verify / troubleshoot:

1. **R binary + system libs** (`r-base`, `libgdal-dev`, `libproj-dev`, etc.) are installed during the image build. No action from you.

2. **R packages** install automatically on first container creation via `postCreateCommand`, which runs `sudo Rscript .devcontainer/install_r_packages.R`. This takes **~15-20 minutes** the first time and runs in the background — you can use the editor for non-R work (Python tests, editing, terminal) while it finishes.

3. **Packages persist across container recreations** in a docker volume named `equitable-polling-locations_r-site-library`, so the 15-minute install only happens once per developer. Rebuilding the image does not wipe the volume.

**Verify R is ready:**

```bash
Rscript R/tests/r_smoke_test.R
```

Expected output: `OK: R 4.3.x with 17 packages loadable`.

**If the smoke test reports missing packages:**

Check whether the background install is still running:

```bash
ps -ef | grep Rscript | grep -v grep
```

- **Running:** wait for it to finish (tail `/tmp/r-install.log` if postCreate redirected output there, otherwise just periodically rerun the smoke test)
- **Not running:** the initial postCreate died silently. Kick it off manually:
    ```bash
    sudo Rscript .devcontainer/install_r_packages.R
    ```

**To force a clean R package reinstall** (e.g. if a package gets corrupted), wipe the docker volume from the **host terminal** and restart the container:

```bash
docker volume rm equitable-polling-locations_r-site-library
```

The next container start re-runs the full install.

**Adding or removing R packages** later — see [Adding or updating R packages](#adding-or-updating-r-packages).

**Using R outside the Dev Container** — see [Working outside the Dev Container](#working-outside-the-dev-container).

**Rebuilding after `.devcontainer/Dockerfile` or `environment.yml` changes:**

- **VS Code users:** Command Palette → `Dev Containers: Rebuild Container`. VS Code builds the new image automatically. Nothing else to do.
- **Zed users:** Rebuild the image manually first (see [Zed caveats](#zed-caveats)), then close the window, `docker rm -f equitable_polling_locations-app-1`, and reopen in Zed.

The R packages persist in a docker volume independently of the image, so they don't reinstall on image rebuild. To force a clean R reinstall: `docker volume rm equitable-polling-locations_r-site-library`.

**What's in the container:**

- Python 3.11 + the pinned conda env `equitable-polls` (pytest, pylint, geopandas, etc.) — baked into the image
- **R 4.3** + the project's R packages (`data.table`, `sf`, `ggplot2`, `bigrquery`, `lintr`, `styler`, `languageserver`, etc. — see `.devcontainer/install_r_packages.R`) — R binary baked into image; packages installed on first container start and persisted in a docker volume
- Node.js 20 + `claude` CLI (for [Claude Code](#claude-code))
- Git + Git LFS + `gh` CLI (GitHub CLI — used as git's credential helper for HTTPS operations; see [Git from inside the container](#git-from-inside-the-container-optional))
- **gcloud CLI + auth state** persisted in a docker volume (`gcloud-config`), isolated from host — run `gcloud auth application-default login --no-launch-browser` once per machine; credentials feed BigQuery and other GCP calls automatically via `GOOGLE_APPLICATION_CREDENTIALS`
- **gh auth state** persisted in a docker volume (`gh-config`), isolated from host — `gh auth login` once per machine, no host SSH keys needed
- **Claude Code state** persisted in a docker volume (`claude-state`), isolated from host Claude — container auth, MCP servers, and plugins survive rebuilds and don't cross-contaminate with your host Claude install

**Using the container's integrated terminal:**

Both VS Code and Zed open the editor's integrated terminal *inside* the running container — no SSH, no `docker exec`, no prefixing commands with `docker compose run`. The conda env is already active on `PATH`, so you can run project tools directly.

How to open the terminal:

- **VS Code:** press ``Ctrl+` `` (backtick), or *View → Terminal*, or Command Palette → `Terminal: Create New Terminal`
- **Zed:** press ``Ctrl+` ``, or *View → Toggle Terminal*

To confirm the terminal is inside the container, the prompt should look like `vscode@<container-id>:/workspaces/Equitable-Polling-Locations $`. You can double-check with:

```bash
whoami       # prints: vscode
uname -a     # prints a Linux kernel (even on a Mac or Windows host)
pwd          # prints: /workspaces/Equitable-Polling-Locations
```

Common commands to run in the container terminal:

```bash
# Run tests
pytest                              # all unit + e2e tests
pytest python/tests/model_data_test.py
pytest python/tests/e2e/ -m e2e_csv

# Lint
pylint python/

# CLI scripts (the script runs in the same container, not a new one)
python -m python.scripts.model_run_cli -c 5 -l ./datasets/configs/Gwinnett_GA/config.yaml

# Claude Code
claude

# Python REPL with the project env loaded
python
```

`run.py` also works inside the container — it detects `/.dockerenv` and runs commands directly instead of trying to spawn another container. So `python run.py test`, `python run.py lint`, `python run.py r_test`, and `python run.py <script_name>` all work identically whether you invoke them from the host or from inside the dev container. Use whichever is convenient.

### Local Development with Conda (optional)

> Skip this section if you're using Docker (the recommended path) — `run.py` already provides everything below inside the container.

Conda can be set up for local development without Docker. This is useful for IDE integration and debugging.

1. Install conda if you do not have it already
    - This project uses SCIP as an optimizer, which is easily installed using conda but not using pip
    - If you do not have conda installed already, use the relevant instructions [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html)
2. Create and activate the conda environment (on Windows, use Anaconda Prompt):
    ```bash
    conda env create -f environment.yml
    conda activate equitable-polls
    ```

#### Updating the conda environment

When `environment.yml` changes (a dependency is added, removed, or pinned to a new version), sync your local env rather than recreating it:

```bash
conda activate equitable-polls
conda env update -f environment.yml --prune
```

`--prune` removes packages that are no longer listed in `environment.yml`, keeping your env in lockstep with the file. If the update fails or the env drifts badly, fall back to a clean rebuild:

```bash
conda deactivate
conda env remove -n equitable-polls
conda env create -f environment.yml
```

Docker and Dev Container users: the conda env is baked into the image, so `environment.yml` changes are picked up at image rebuild. Rebuild from a host terminal with `docker compose -f .devcontainer/docker-compose.build.yml build`, then rebuild the container in your editor (VS Code: *Dev Containers: Rebuild Container*; Zed: close the window, `docker rm -f equitable_polling_locations-app-1`, reopen). A rebuilt image benefits both the dev container and host-invoked `run.py` — they share one image.

### IDE Setup for Local Conda (optional)

> If you're using the [Dev Container](#dev-container--vs-code-or-zed-recommended-for-editor-integrated-development), skip this section — everything below is already configured automatically inside the container.

For inline diagnostics and type/lint feedback while editing against a local conda environment, point your IDE at the `equitable-polls` conda environment's Python interpreter. The editor will pick up Pylint from that environment along with the project's `.pylintrc`.

**VS Code:**

1. Install the [Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) and the [Pylint extension](https://marketplace.visualstudio.com/items?itemName=ms-python.pylint) (VS Code will prompt you — these are in `.vscode/extensions.json`)
2. Command Palette → `Python: Select Interpreter` → choose the `equitable-polls` conda environment
3. Pytest discovery and inline **▶ Run Test** / **🐞 Debug Test** buttons come from `.vscode/settings.json` (already committed)
4. The Pylint extension auto-detects `.pylintrc` at the project root

**Zed:**

1. Zed ships with Python language server support out of the box
2. Command Palette → select toolchain → choose the `equitable-polls` conda environment's Python interpreter
3. Project-level settings in `.zed/settings.json` and pytest/pylint tasks in `.zed/tasks.json` are already committed. See the [Zed Python docs](https://zed.dev/docs/languages/python) for additional options.

If you prefer running pylint outside the editor, use `python run.py lint` (see [Linting](#linting)).

### Database Setup (optional)

Database-backed workflows require GCP Application Default Credentials and a configured environment in `settings.yaml`.

- **Authenticate inside the container** via device flow. From the container's integrated terminal:
    ```bash
    gcloud auth application-default login --no-launch-browser
    ```
    gcloud prints a URL — open it in your host browser, approve the consent, copy the returned verification code, and paste it back in the container. Credentials are saved to the `gcloud-config` docker volume and persist across container rebuilds (re-authenticate only if you `docker volume rm` the volume).
- Use **scratch datasets** for development and testing — never develop directly against production
- Run `alembic upgrade head` to initialize or update the database schema

See [Database](docs/database.md) for full documentation on schema, imports, scratch dataset setup, and Alembic migrations.

### R Package Management

R packages are managed by [renv](https://rstudio.github.io/renv/). The repo's `renv.lock` is the canonical pinned package set (covers ~129 packages, including transitives). The dev container's `postCreateCommand` (`run_r_install.sh`) bootstraps renv and runs `renv::restore()` against `renv.lock` automatically, so no manual setup is needed inside the container.

**To add a new R package:**

```bash
Rscript -e 'renv::install("pkg-name")'
Rscript -e 'renv::snapshot()'    # captures the new state into renv.lock
```

Then commit `renv.lock`. The R smoke test (`python run.py r_test`) reads its package list from `renv.lock` directly, so there's no separate list to keep in sync.

**To update an existing R package:**

```bash
Rscript -e 'renv::install("pkg-name@x.y.z")'   # specific version
# or
Rscript -e 'renv::update("pkg-name")'           # latest compatible
Rscript -e 'renv::snapshot()'
```

Then commit `renv.lock`.

**Smoke-testing the R env:**

```bash
python run.py r_test
```

Loads every package in `renv.lock` and reports any that fail to load.


## Code Style

### Python

This project follows the [Google Python style guide](https://google.github.io/styleguide/pyguide.html) for all new code. Pylint (see `.pylintrc`) is the project's linter and should be run before merges via `python run.py lint`.

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

This project is adopting [Conventional Commits](https://www.conventionalcommits.org/). Examples:

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
python run.py test
```

Or locally with a conda environment:

```bash
pytest
```

If you're using the [Dev Container](#dev-container--vs-code-or-zed-recommended-for-editor-integrated-development), you can also run and debug individual tests directly from the editor via the **▶ Run Test** / **🐞 Debug Test** buttons that appear above each `def test_*` function.

### End-to-End (E2E) Tests

E2E tests exercise the full CLI scripts via subprocess, verifying that each command produces correct output files and database records. They live in `python/tests/e2e/`.

Test data is automatically templated from `datasets/polling/testing/` with a unique session ID per run, so multiple test runs (even concurrent ones) will not interfere with each other.

There are two categories of E2E tests:

- **CSV tests (`e2e_csv`)** — Test CSV-based workflows (`model_run_cli`, `auto_generate_config`). These always run and require no external dependencies.
- **DB tests (`e2e_db`)** — Test database-backed workflows (`db_import_*_cli`, `model_run_db_cli`). **Prerequisites:** a `test` environment configured in `settings.yaml` and valid GCP Application Default Credentials — see [Setting Up DB Tests](#setting-up-db-tests) below. Behavior when DB setup is missing depends on how the tests are invoked:
    - **Mixed runs** (e.g. `python run.py e2e_tests` with no marker, or `-m e2e_csv`): DB tests skip gracefully so offline development keeps working.
    - **DB-only runs** (e.g. `python run.py e2e_tests -m e2e_db`, or pointing pytest at a DB-only test file): missing `settings.yaml` or no `test:` entry **aborts the session with an error**. Opting into DB tests without configuring them is treated as a usage error, not silently skipped.
    - **Connection failures** when `settings.yaml` *is* configured (expired credentials, network issues, etc.): tests **error** rather than skip — a configured environment is an opt-in declaration that the DB should be reachable.

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

#### Inspecting E2E Outputs

By default the E2E suite cleans up every file and directory it generates after the session finishes. Pass `--keep-e2e-outputs` to skip the filesystem cleanup and inspect the inputs and outputs of each run — useful when a test fails and you want to look at what the solver actually produced, or when you want to reproduce a single run by hand.

```bash
# Host
python run.py e2e_tests -m e2e_csv --keep-e2e-outputs

# Dev container or local conda
pytest python/tests/e2e/ -m e2e_csv --keep-e2e-outputs
```

Each session is namespaced by a random ID `e2e_<6 hex chars>` and writes to four directories under `datasets/`:

| Path | Contents |
| --- | --- |
| `datasets/polling/e2e_<sid>/` | Inputs the run consumed: copied potential locations CSV plus 8 distance CSV variants |
| `datasets/driving/e2e_<sid>/` | Source driving distances CSV |
| `datasets/configs/e2e_<sid>/` | 8 generated YAML configs plus 1 autogen template (the inputs each test fed into the solver) |
| `datasets/results/e2e_<sid>_results/` | **Model outputs** — `_results.csv`, `_precinct_distances.csv`, `_residence_distances.csv`, `_edes.csv` for each variant |

The `_results/` directory is usually the most useful for debugging. To reproduce a single run by hand:

```bash
python run.py model_run_cli -c 1 -l ./datasets/configs/e2e_<sid>/e2e_<sid>_config_basic.yaml
```

The four directories are gitignored (see the `e2e_*` rules in `.gitignore`), so retained outputs will not show up in `git status` or be accidentally committed.

**Cleanup when you're done:**

```bash
rm -rf datasets/polling/e2e_* datasets/driving/e2e_* datasets/configs/e2e_* datasets/results/e2e_*_results
```

The flag does **not** affect database cleanup — the `e2e_db` session still purges its BigQuery rows at start and end as described in [Setting Up DB Tests](#setting-up-db-tests) below.

#### Setting Up DB Tests

To run the DB E2E tests:

1. Ensure `settings.yaml` has a `test` environment configured (see `settings_example.yaml`)
2. Ensure GCP Application Default Credentials are set up **inside the container** — see [Database Setup](#database-setup-optional) for the in-container `gcloud auth application-default login --no-launch-browser` flow. Credentials persist in the `gcloud-config` docker volume.
3. Run via `python run.py e2e_tests -m e2e_db` — whether invoked from the host or from inside the container, the tests pick up credentials from the volume automatically.

DB tests do not auto-clean their data — `e2e_`-prefixed rows accumulate in the test dataset across runs so they're available for manual inspection and feature-development work. Run an on-demand purge when the dataset gets bulky (no script ships with the repo today; a `bq query` against `tests_chad` filtered by `WHERE config_set LIKE 'e2e_%'` is the simplest interim approach).

### Pre-Merge Checklist

Before merging any change, run:

```bash
python run.py test
pylint python/
```

All tests and lints must pass.


## Linting

### Python

Pylint is bundled with the project's Python environment via `environment.yml`, so Docker and conda users get it automatically.

**Docker (recommended):**

```bash
python run.py lint
```

**Local conda environment:**

```bash
conda activate equitable-polls
pylint python/
```

**Other setups** (neither Docker nor conda): install Pylint manually, then run it:

```bash
pip install pylint
pylint python/
```

Pylint reads rules from `.pylintrc` at the project root (Google Python style).

- **Warnings are errors** — fix all Pylint warnings. Do not add `# pylint: disable` without a comment explaining why the suppression is necessary.
- Run pytest with `-W error` to catch Python warnings as test failures.

### R

R, along with `lintr`, `styler`, and all the R packages used by the analysis scripts, is pre-installed inside the [Dev Container](#dev-container--vs-code-or-zed-recommended-for-editor-integrated-development).

#### Running R in the container

From the container's integrated terminal (``Ctrl+` ``):

```bash
# Interactive R REPL
R

# Run a one-off script
Rscript path/to/script.R

# Smoke-test that R and all packages are loadable
Rscript R/tests/r_smoke_test.R
```

#### Running R from the IDE

**Zed:** R tasks are pre-configured in `.zed/tasks.json`. Open the command palette (Cmd+Shift+P) → `task: spawn` → pick one:

| Task | What it does |
|------|-------------|
| **R: smoke test** | Verifies all 16 R packages load correctly |
| **R: run current file** | Runs whichever `.R` file is open via `Rscript` |
| **R: lint current file** | Runs `lintr::lint()` against the open `.R` file |

Zed does not have inline R play buttons (no R language server integration); use tasks or the terminal REPL for interactive work.

**VS Code:** Install the [R extension](https://marketplace.visualstudio.com/items?itemName=REditorSupport.r) for syntax highlighting, an integrated R terminal, an inline plot pane, and send-to-REPL line execution. You can also run R scripts via the built-in terminal.

#### Running R from the host

From the **host** (Mac/Linux/WSL), you can invoke R in the dev container image without opening an editor:

```bash
# Smoke-test that R is set up correctly
python run.py r_test

# Run an R script inside a one-shot container
docker compose -f .devcontainer/docker-compose.yml run --rm app Rscript path/to/script.R
```

#### Linting and formatting

From an R session, `Rscript -e`, or the Zed lint task:

```r
lintr::lint("path/to/file.R")
styler::style_file("path/to/file.R")
```

#### Adding or updating R packages

The package list lives in `.devcontainer/install_r_packages.R`. This script runs automatically via `postCreateCommand` on first container creation, installing the latest versions from CRAN into a docker volume mounted at `/usr/local/lib/R/site-library` so packages persist across container recreations.

To add or update a package (in the dev container):

1. Edit the `packages` vector in `.devcontainer/install_r_packages.R`
2. Add the same package to `R/tests/r_smoke_test.R`
3. Install it now: `sudo Rscript .devcontainer/install_r_packages.R`
4. Verify: `Rscript R/tests/r_smoke_test.R`
5. Commit `install_r_packages.R` and `r_smoke_test.R`

**Force a clean R package reinstall** (e.g. if a package is in a bad state): from the host terminal, remove the docker volume, then rebuild the container:

```bash
docker volume rm equitable-polling-locations_r-site-library
```

The next time the container starts, `postCreateCommand` will reinstall all packages from scratch (~15-20 min).

#### Working outside the Dev Container

If you prefer a local R install, install the packages manually using the list in `.devcontainer/install_r_packages.R`:

```r
source(".devcontainer/install_r_packages.R")
```

Versions are not pinned — you'll get whatever CRAN ships at install time. If you need reproducibility across machines, consider setting up [renv](https://rstudio.github.io/renv/) locally.


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

All pull requests require review by a maintainer from Voting Rights Code before merge.

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

You can run Claude Code either on your host system or inside the dev container. Use whichever fits your workflow; both work against the same repository.

**Inside the Dev Container (recommended if you already develop in-container):**

The `claude` CLI is pre-installed in the image (baked in at build time via `.devcontainer/Dockerfile`). To start it:

1. **Open the project in your editor in the container:**
    - **VS Code:** open the project folder → click *Reopen in Container* if prompted, or Command Palette → `Dev Containers: Reopen in Container`
    - **Zed:** open the project folder. Zed detects `.devcontainer/devcontainer.json` and attaches to (or builds) the container automatically. When it finishes, you'll be "inside" the container.
    - If this is the first time, the container will build (several minutes — conda solve + Node install + Claude install). Subsequent opens reuse the existing container and take seconds.

2. **Open the integrated terminal inside the container:**
    - Press ``Ctrl+` `` (backtick) in either editor. See [Using the container's integrated terminal](#dev-container--vs-code-or-zed-recommended-for-editor-integrated-development) for other ways to open it and how to verify you're inside the container.

3. **Start Claude Code:**
    ```bash
    claude              # interactive session
    claude --help       # command-line help
    ```
    On first run, Claude Code prompts you to authenticate via a browser. Follow the link it prints, log in, and paste the returned code back into the terminal. `Ctrl+D` or typing `/exit` ends the session.

**Your Claude Code state lives in an isolated docker volume** (`claude-state`), separate from your host's `~/.claude/`. Container and host can run different Claude versions, install different plugins, and authenticate independently without interfering with each other. The volume survives container recreations and image rebuilds, so you only need to log in once per machine (or once after `docker volume rm`).

- **First run in the container:** `claude` will prompt you to authenticate via browser. Log in once; subsequent runs read the saved auth from the volume.
- **Plugins and MCP servers installed on your host DO NOT appear in the container** (and vice versa). Install them separately inside the container via `/plugins` and `claude mcp add` if you need them in both places. See [GitHub MCP Server](#github-mcp-server) below for an example.
- **To reset the container's Claude state** (forget auth, plugins, MCP config): from the **host terminal**, `docker volume rm equitable-polling-locations_claude-state`, then restart the container. Next `claude` run will prompt for login again.

**On the host (alternative):**

Install Claude Code following the official instructions at [claude.ai/download](https://claude.ai/download). Use this if you prefer to keep AI tooling outside the container entirely. Host and container Claude installs are now fully independent — changes to one don't affect the other.

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

The following plugins from `claude-plugins-official` are declared in `.claude/settings.json`'s `enabledPlugins` block:

- **superpowers** — planning, code review, and development workflow skills
- **commit-commands** — commit, push, and PR shortcuts
- **pyright-lsp** — Python type checking and language server integration

`.devcontainer/post-create.sh` registers the `claude-plugins-official` marketplace and pre-installs these on first container boot, so they are ready the first time you run `claude`. A fresh `claude-state` volume has no marketplaces registered by default — without post-create.sh, the declared plugins would silently fail to resolve. To force a reinstall (e.g., after `docker volume rm equitable-polling-locations_claude-state`), rerun `bash .devcontainer/post-create.sh` inside the container or rebuild the container.

To see or manage the installed plugin set interactively, run `/plugins` inside a Claude session.


## Getting Help

- **Discord:** [Ask us on Discord](https://discord.com/channels/1106301559811350540/1106301560507609241) — we'd love to talk to you, even if you're just browsing
- **Check in early:** If you're unsure who else is working on a relevant part of the project, ask. If you don't understand how someone else is approaching a problem, ask them.
- **We ask for help when we need it, and get it.** Don't hesitate to reach out.
