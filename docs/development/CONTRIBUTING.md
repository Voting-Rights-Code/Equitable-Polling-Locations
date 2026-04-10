# Contributing — Development Guide


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

There are two categories of e2e tests:

- **CSV tests (`e2e_csv`)** — Test CSV-based workflows (`model_run_cli`, `auto_generate_config`). These always run and require no external dependencies.
- **DB tests (`e2e_db`)** — Test database-backed workflows (`db_import_*_cli`, `model_run_db_cli`). These require a `test` environment configured in `settings.yaml` and valid GCP credentials. They skip gracefully when either is unavailable.

#### Running E2E Tests

Via Docker (recommended):

```bash
# All e2e tests
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

To run the DB e2e tests:

1. Ensure `settings.yaml` has a `test` environment configured (see `settings_example.yaml`)
2. Ensure GCP Application Default Credentials are set up (`gcloud auth application-default login`)
3. Run via `python run.py e2e_tests -m e2e_db` — the `run.py` wrapper mounts GCP credentials into the Docker container automatically

DB tests clean up after themselves by deleting all `e2e_`-prefixed data from the test dataset at both the start and end of each session.


## Development

Conda can be optionally setup for local development without docker.

1. Install conda if you do not have it already
    1. This program uses SCIP as an optimizer, which is easily installed using Conda, but not using pip. (SCIP installation will be completed below by installing 'environment.yml')
    1. If you do not have conda installed already, use the relevant instructions [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html)

1. Create and activate conda environment. (Note, on a Windows machine, this requires using Anaconda Prompt.)
    1. `$ conda env create -f environment.yml`
    1. `$ conda activate equitable-polls`


## Claude Code

### Install

Install Claude Code following the official instructions at [claude.ai/download](https://claude.ai/download).

### GitHub MCP Server

Claude Code uses the GitHub MCP server to create and manage issues and pull requests. To set it up:

1. **Generate a fine-grained personal access token:**
    1. Go to [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta)
    1. Click **Generate new token**
    1. Under **Repository access**, select **Only select repositories** and choose `Voting-Rights-Code/Equitable-Polling-Locations`
    1. Under **Permissions → Repository permissions**, grant:
        - **Issues** — Read and write
        - **Pull requests** — Read and write
    1. Click **Generate token** and copy it

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
