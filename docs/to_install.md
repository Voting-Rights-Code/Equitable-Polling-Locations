## Installation
1. Clone main branch of Equitable-Polling-Locations
    1. This repo uses lfs. This can be downloaded from [https://git-lfs.com/](https://git-lfs.com/).
        1. Download the appropriate version from this website and follow the instructions included there.
        1. If those instructions don't work, (as may be the case on Linux or MacOS), run ```sudo ./install.sh``` after downloading the file, then follow the instructions above. See [here](https://stackoverflow.com/questions/58796472/git-lfs-is-not-a-git-command-on-macos).
1. Install Docker from [https://www.docker.com/](https://www.docker.com/)
    1. Windows:
       1. In the Windows Subsystem for Linux set the memory to at least 8gb in the ```.wslconfig``` in the ```%USERPROFILE%``` directory.
    1. MacOS:
       1. In the docker desktop app, under resources set the memory to at least 8gb.
1. Environment settings file `settings.yaml`
    1.  The settings file allows you to configure different environments to connect to such as dev or prod, and have each environment connect to a different database or dataset.
    1.  Copy the ```settings_example.yaml``` to ```settings.yaml```
    1.  Additional environments may be configured as necessary.

### Census API Key (optional, for new counties)

If you plan to download census data for counties not already in the repo, you need a free census API key.

1. [Apply for a census API key](https://api.census.gov/data/key_signup.html) (approved in seconds)
2. Install keyring on your host machine: `pip install keyring`
3. Store your key: `python run.py set_census_key`
4. Use `-k` when running scripts that need census data: `python run.py -k <script> [args]`

The `-k` flag caches the key locally in `authentication_files/credentials.json` (gitignored), so you only need to pass `-k` once. Subsequent runs will use the cached file.

### Test the Installation
To confirm the installation is setup correctly, run pytest with the following command in the root of the project directory:

```
docker compose run --rm app pytest
```

All tests should pass.


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




