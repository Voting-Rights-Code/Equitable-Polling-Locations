# End-to-End CLI Test Suite Design

**Date:** 2026-03-18
**Branch:** `feature/cli-e2e-tests`
**Status:** Draft

## Problem

Testing the CLI tools is a manual, tedious process. There are no automated tests that exercise the actual CLI entry points (`model_run_cli`, `db_import_*_cli`, etc.) or verify the full pipeline: import data, run model, check results. The existing pytest suite tests solver internals via fixtures but never invokes a script as a subprocess.

## Goals

1. Automated end-to-end tests that invoke CLI scripts as subprocesses, testing real entry points.
2. CSV-based tests that always run (no external dependencies).
3. DB-based tests that run when a `test` environment is configured in `settings.yaml`, skipping gracefully otherwise.
4. Tests can run individually (single script) or as a full pipeline suite.
5. Tests work both inside Docker (`run.py e2e_tests`) and locally (`pytest`).
6. Concurrent test runs against the same DB dataset do not interfere with each other.

## Approach

Pytest fixture dependency chain with session-scoped fixtures. Each CLI script gets its own test file declaring fixture dependencies. Pytest resolves the dependency graph automatically — running a single test file triggers only the prerequisite fixtures it needs.

## Test Organization

### Directory Structure

```
python/tests/e2e/
  conftest.py                          # Shared fixtures, skip logic, helpers
  test_model_run_cli.py                # CSV model runs with various config options
  test_auto_generate_config.py         # Config generation from templates
  test_db_import_potential_locations.py # Import potential locations to DB
  test_db_import_driving_distances.py  # Import driving distances to DB
  test_db_import_distance_data.py      # Import combined distance data to DB
  test_db_import_config.py             # Import YAML configs to DB
  test_model_run_db_cli.py             # DB-backed model runs
```

### Pytest Markers

- `@pytest.mark.e2e` — all e2e tests
- `@pytest.mark.e2e_csv` — CSV/local tests only (always run)
- `@pytest.mark.e2e_db` — DB tests only (skip if no test environment)

### Skip Logic

- DB tests: skip if no `test` entry in `settings.yaml` with message `"No 'test' environment in settings.yaml — skipping DB tests"`
- CSV tests: always run, no external dependencies

## Session Data Templating

### Session Isolation

Each test session generates a unique ID: `e2e_{uuid4_hex[:6]}` (e.g., `e2e_a3f7b2`). This ID becomes the `location`, `config_set`, and prefix for all config names. This ensures concurrent test runs against the same BigQuery dataset do not collide.

### Templating Process (session-scoped `e2e_test_data` fixture)

1. Create a temp directory structure:
   ```
   {tmpdir}/
     polling/{session_id}/
       {session_id}_potential_locations.csv
       {session_id}_distances_2020.csv
       {session_id}_driving_2020.csv
     configs/{session_id}/
       {session_id}_config_basic.yaml
       {session_id}_config_driving.yaml
       {session_id}_config_penalty.yaml
       {session_id}_config_log.yaml
       {session_id}_config_driving_log.yaml
       {session_id}_config_low_beta.yaml
       {session_id}_config_capacity.yaml
       {session_id}_config_constrained.yaml
     configs/template_configs/
       {session_id}_template.yaml_template
   ```

2. CSVs are copied from `datasets/polling/testing/` and `datasets/driving/testing/` — no content changes needed since location is set in the config, not in the CSV data.

3. YAML configs are generated from existing `datasets/configs/testing/*.yaml` files with substitutions:
   - `config_set` → `{session_id}`
   - `config_name` → `{session_id}_{variant}`
   - `location` → `{session_id}`
   - Option-specific fields adjusted per variant.

4. Template config generated similarly for `auto_generate_config` tests.

### Config Variants

| Config name suffix | beta | driving | log_distance | capacity | maxpctnew | minpctold | bad_types | penalized_sites |
|---|---|---|---|---|---|---|---|---|
| `_basic` | -2 | false | false | 5 | 1 | 0.5 | [bg_centroid] | [] |
| `_driving` | -2 | true | false | 5 | 1 | 0.5 | [bg_centroid] | [] |
| `_log` | -2 | false | true | 5 | 1 | 0.5 | [bg_centroid] | [] |
| `_driving_log` | -2 | true | true | 5 | 1 | 0.5 | [bg_centroid] | [] |
| `_penalty` | -2 | false | false | 5 | 1 | 0.5 | [bg_centroid] | [site] |
| `_low_beta` | -1 | false | false | 5 | 1 | 0.5 | [bg_centroid] | [] |
| `_capacity` | -2 | false | false | 3 | 1 | 0.5 | [bg_centroid] | [] |
| `_constrained` | -2 | false | false | 5 | 0.5 | 0.75 | [bg_centroid] | [] |

## Fixture Dependency Chain

```
test_environment  (loads & validates 'test' env from settings.yaml)
    │
    └── clean_test_data  (deletes all e2e_%-prefixed rows from DB)
            │
            ├── imported_potential_locations  (runs db_import_potential_locations_cli)
            │       │
            │       ├── imported_driving_distances  (runs db_import_driving_distances_cli)
            │       │       │
            │       │       └── imported_distance_data  (runs db_import_distance_data_cli, all permutations)
            │       │               │
            │       │               └── imported_configs  (runs db_import_config_cli)
            │       │                       │
            │       │                       └── [test_model_run_db_cli tests]
            │       │
            │       └── imported_distance_data_haversine  (haversine-only variant)
            │
            (no DB needed)
            ├── [test_model_run_cli — uses templated test data]
            ├── [test_auto_generate_config — uses templated template configs]
```

### DB Cleanup Strategy

- `clean_test_data` fixture runs at session start, before any imports
- Deletes all rows where `config_set` or `location` matches `e2e_%` pattern
- Covers all tables: model_configs, model_runs (cascades to results/edes/precinct_distances/residence_distances), potential_locations_sets (cascades to potential_locations), driving_distance_sets (cascades to driving_distances), distance_data_sets (cascades to distance_data)
- Garbage collects all `e2e_*` data from any session, not just current — handles stale data from crashed runs

### Distance Data Import Permutations

| Import variant | -t flag | -d flag | Used by configs |
|---|---|---|---|
| haversine linear | linear | no | `_basic`, `_penalty`, `_low_beta`, `_capacity`, `_constrained` |
| haversine log | log | no | `_log` |
| driving linear | linear | yes | `_driving` |
| driving log | log | yes | `_driving_log` |

## CLI Script Invocation

All tests call scripts via `subprocess.run(["python", "-m", "python.scripts.<script_name>", ...])`. A shared helper in `conftest.py` wraps this with:
- Standard error handling (assert exit code, capture stdout/stderr)
- Output capture included in pytest failure messages
- Logging of all invocations for post-mortem debugging

## CLI Option Coverage

### test_model_run_cli.py

- Basic run with single config
- Multiple configs in one invocation
- Concurrent runs (`-c 2`)
- Verbose logging (`-vv`)
- Custom log directory (`-L`)
- Config variations: beta, driving, log_distance, bad_types, capacity, maxpctnew/minpctold, penalized_sites

### test_model_run_db_cli.py

- Output to CSV (`-o csv`)
- Output to DB (`-o db`)
- Config as `config_set` (all configs in set)
- Config as `config_set/config_name` (single config)
- Verbose and concurrent options

### test_db_import_potential_locations.py

- Import test locations file
- Verify DB records match CSV

### test_db_import_driving_distances.py

- Import driving distances
- Verify record count and values

### test_db_import_distance_data.py

- All permutations: linear without driving, log without driving, linear with driving, log with driving
- Verify record counts, distance types, demographic columns per permutation

### test_db_import_config.py

- Import single config YAML
- Import multiple config YAMLs
- Verify DB fields match YAML source

### test_auto_generate_config.py

- Generate configs from template (varying a parameter)
- Verify correct number of output YAMLs (cartesian product)
- Verify generated config values match expected
- With `-d` flag: configs appear in DB (if test environment available)

## Assertion Strategy

### Smoke-Level (all scripts)

- CLI exits with code 0
- Expected output files exist (CSV-outputting commands)
- Expected DB records exist (DB-importing commands)
- Outputs are non-empty

### Value-Level (model runs)

- **Result outputs:** correct columns, all residences assigned, no duplicate assignments
- **EDE outputs:** all demographic groups present, positive floats for y_ede and avg_distance
- **Precinct distances:** count matches `precincts_open`
- **Residence distances:** count matches unique `id_orig` in source data
- **Constraint verification:**
  - Open precincts matches `precincts_open`
  - New locations within `maxpctnew` ratio
  - Old locations meet `minpctold` ratio
  - No precinct exceeds `capacity`
  - Penalized sites excluded when configured
- **Cross-config comparisons:**
  - `_low_beta` vs `_basic`: different EDE values (beta has effect)
  - `_driving` vs `_basic`: different distances (driving distances used)
  - `_log` vs `_basic`: different distances (log transform applied)

### DB Import Assertions

- `db_import_potential_locations`: record count matches CSV, lat/lon spot-checked
- `db_import_driving_distances`: record count matches CSV, distance values spot-checked
- `db_import_distance_data`: record count per permutation, demographic columns populated, distance source type correct
- `db_import_config`: all config fields in DB match YAML source

### Auto Generate Config Assertions

- Correct number of output YAMLs
- Varied field set to expected values
- Non-varied fields unchanged
- With `-d`: configs in DB with correct values

## Test Execution

### Via Docker (recommended)

```bash
# All e2e tests
python run.py e2e_tests

# CSV tests only
python run.py e2e_tests -m e2e_csv

# DB tests only
python run.py e2e_tests -m e2e_db

# Single test file
python run.py e2e_tests python/tests/e2e/test_model_run_cli.py

# Preserve output for inspection
python run.py e2e_tests --basetemp=./e2e_output
```

### Locally (conda environment)

```bash
pytest python/tests/e2e/
pytest python/tests/e2e/ -m e2e_csv
pytest python/tests/e2e/test_db_import_distance_data.py
```

### run.py Changes

- `e2e_tests` added as a special command
- Translates to `docker compose run --rm app pytest python/tests/e2e/ [extra args]`
- Passes through additional arguments (`-m`, `-k`, `-v`, file paths, etc.)

## Output & Debugging

- CLI stdout/stderr captured and included in pytest failure output
- Session log of all CLI invocations and exit codes
- Temp directory holds all generated data; preserved with `--basetemp` for inspection
- Verbose pytest (`-v`) shows fixture setup order, making dependency chain visible
