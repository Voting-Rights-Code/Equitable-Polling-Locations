# Running the Program

This guide covers how to run the Equitable Polling Locations model from the command line. The model is invoked through the `run.py` wrapper, which executes scripts inside a Docker container so you don't need to manage Python dependencies yourself.

## Prerequisites

The program runs inside Docker via the `run.py` wrapper. Before running the model:

1. Install [Docker Desktop](https://www.docker.com/) and make sure it is running.
    - Allocate at least **8 GB of RAM** to Docker (Docker Desktop → Settings → Resources on Mac/Windows, or `.wslconfig` on Windows with WSL).
2. Clone this repository. It uses [Git LFS](https://git-lfs.com/) for large data files, so install Git LFS first, then run `git lfs install` once before cloning.
3. If you have access to the database, copy `settings_example.yaml` to `settings.yaml` in the project root. Else do nothing and run locally.
4. Create the requisite input files discussed in [input files](input_files.md).

See [Installation](to_install.md) for more detail.

> **Local (non-Docker) execution** is also supported via a conda environment. See [Contributing — Development Guide](../CONTRIBUTING.md#development-environment) for setup.

## Managing Secrets

`run.py` provides a `secret` command for storing and retrieving named credentials. The only registered secret today is `census` (your Census API key).

At model-run time, host-launched `run.py` resolves each secret using this precedence — **env var > OS keyring > credentials file** — and forwards it into the container automatically (the container reads `CENSUS_API_KEY`). Working **inside** the dev container? `keyring` is host-only and nothing is auto-forwarded there, but `secret set` also writes the bind-mounted `authentication_files/credentials.json`, so a single host-side `secret set` makes the value available in the container. If `git clean -fdx` removes that file, run `python run.py secret restore` on the host to rebuild it from the keyring (see [Installation — keyring backend](to_install.md#optional-keyring-backend)).

### Census API Key

The model needs a free [census API key](https://api.census.gov/data/key_signup.html) whenever it has to pull demographics or TIGER shapefiles for a county that isn't already in `datasets/census/`. If you're only re-running an existing config against data that's already on disk (or in the database), you can skip this section.

**Store the key** (one-time, interactive prompt):

```bash
python run.py secret set census
```

**Check whether the key is set** (prints a masked value by default):

```bash
python run.py secret get census
python run.py secret get census --show   # prints the raw value
```

**Remove the key from all backends:**

```bash
python run.py secret clear census
```

**Rebuild `credentials.json` from the keyring** (host-side, after `git clean -fdx` wipes the file):

```
python run.py secret restore
```

**Alternative — environment variable.** Export `CENSUS_API_KEY` instead — it takes precedence over the stored secret and is useful inside containers and CI:

```bash
export CENSUS_API_KEY=your-key-here
python run.py pull_census_data_cli TX "Tarrant County" 2020
```

See [Input Data — Census Data](input_files.md#census-data-demographics-and-shapefiles) for the full list of files pulled, and [Installation — Census API Key](to_install.md#census-api-key-optional-for-new-counties) for keyring setup and other install-time details.

## Running the Model

From the project root, run the model. There are two command line options, one to write data locally, and the other to write data to the database:
* Read/write locally: `python run.py model_run_cli -c NUM ./path/to/config/file.yaml`
* Read/write from/to database:
    * `python run.py model_run_db_cli -e ENV -c NUM config_set/config_name1 config_set2/config_name`
    * `python run.py model_run_db_cli -e ENV -c NUM config_set`
* If not all files are already stored in the cloud:
    * If the config file is not stored on the cloud:
        * Run `python run.py db_import_config_cli <./path/to/config/file>`.
        * See [database](database.md) for more details.
    * If the potential locations file is not stored on the cloud:
        * Run `python run.py db_import_potential_locations_cli <list of locations>`
        * See [database](database.md) for more details.
    * If the driving distances file is needed but not stored on the cloud:
        * Run `python run.py db_import_driving_distances_cli <census year> <list of locations>`
        * See [database](database.md) for more details.
    * If the appropriate [intermediate dataset](intermediate_datasets.md) does not exist:
        * Run `python run.py db_import_distance_data_cli <census year> <list of locations> -t <distance type> -d <map date for driving distances>`
        * See [intermediate datasets](intermediate_datasets.md) and [database](database.md) for more details.

## Parameters

* `-e` / `--environment` = The environment to use. For cli utilities that connect to the database, you need to select an environment. Typically this will be "prod" but others can be defined in settings.yaml in the project root directory. If an environment is not provided then you will be prompted to pick one.
* `-c` / `--concurrent` = The number of configurations to run concurrently (default = 1). If more than one is set then multiple model runs can potentially be completed quicker depending on the resources available on your computer.
* path to config file accepts wild cards to set of sequential runs
* config_set and config_name refer to the fields in the config data.
    * To run all the config_names associated to a config_set, just enter the config_set
* To write files locally while using `model_run_db_cli`, use the flag `-o csv`
* `-v` / `--verbose` for extra logging. Stackable: `-v` for verbose output, `-vv` to also enable function timers.
* `-L` / `--logdir` to specify the log file directory (default: `./logs`). When running concurrently (`-c > 1`), logs go to files only to avoid interleaved output.


## Examples

Default execution:\
```python run.py model_run_db_cli -h```

To run all configs in the config_set `Gwinnett_County_GA_driving_no_bg_no_ed_configs`, from the database, parallel processing 4 at a time:\
```python run.py model_run_db_cli -c4 Gwinnett_County_GA_driving_no_bg_no_ed_configs```

To run all configs in the config_set `Gwinnett_County_GA_driving_no_bg_no_ed_configs` locally, one at a time, with extra logging printed to the console:\
```python run.py model_run_cli -vv datasets/configs/Gwinnett_County_GA_driving_no_bg_no_ed_configs/*.yaml```

To run only the config `Gwinnett_County_GA_driving_no_bg_no_ed_14` from the database:\
```python run.py model_run_db_cli Gwinnett_County_GA_driving_no_bg_no_ed_configs/Gwinnett_County_GA_driving_no_bg_no_ed_14```


***NOTE: BEWARE OF CAPITALIZATION***
Both Gwinnett_G**A**_configs/Gwinnett* and Gwinnett_G**a**_configs/Gwinnett* will run on Windows. However, due to string replacement work in other parts of the programs, the former is preferred.

## Generating driving distances

The solver consumes driving-distance CSVs at `datasets/driving/<Loc>_<ST>/<Loc>_<ST>_driving_distances.csv`. The `generate_driving_distances_cli` script builds those CSVs from existing project data (TIGER block centroids + the `<Loc>_<ST>_potential_locations.csv` already used by the solver) by routing every origin × destination pair through a locally-hosted OpenRouteService (ORS) container. **USAGE NOTE:** This CLI is designed to only take local config, `<Loc>_<ST>_potential_locations` and census files, not to read from the database or make census pulls. See [input_files.md](input_files.md) for more information on generating or obtaining these files.

```bash
python3 run.py generate_driving_distances_cli \
  -l datasets/configs/<config_set>/<config>.yaml
```

The state is derived automatically from the config's `location:` field
(`<Name>_<ST>` convention, e.g. `Gwinnett_County_GA` → `georgia`). When using
the `testing` fixture pass an explicit `--testing` override:

```bash
python3 run.py generate_driving_distances_cli --testing \
  -l datasets/configs/testing/testing_config_driving.yaml
```

The first driving run for a state is slow: it downloads a one-time ~13 GB full-US OpenStreetMap extract, clips a state+50 km buffered extract from it (`osmium`), then ORS builds its routing graph (~20-30 min for a large state). Subsequent runs reuse the cached extract and graph (~30s startup). The CLI auto-spawns ORS at the start and tears it down at the end; pass `--keep-ors-running` to leave it up across multiple invocations.

State slugs are full Geofabrik names (`georgia`, `new-york`, `district-of-columbia`); see `python/utils/ors_setup.py` for the full list.

### Unroutable origins fail the run

Every populated census block needs a real driving distance for the solver to run, so an origin ORS cannot route is an error, not a warning. When any origin is unrouted, the CLI still writes the CSV with everything that was successfully computed (completed work is never lost), then **exits non-zero** and prints each missing origin with its id and lat/lon. Fix the underlying data (typically a bad block centroid) and rerun — the resume logic reads the existing CSV and fetches only the missing pairs. Rows patched into the CSV by hand are likewise recognized as satisfied on the next run. Note the check is origin-level: an origin that routes to some destinations but not others is not flagged here; that gap is caught downstream at model-run time. TODO: update after #338 is implemented.


### Manual lifecycle (debugging / repeated experiments)

If you want ORS up persistently:

```bash
python3 run.py build_buffered_extract_cli georgia   # one-time per state: builds georgia-buffered.osm.pbf
python3 run.py ors_up_cli georgia
# ... run generate_driving_distances_cli or curl directly ...
python3 run.py ors_down_cli
```

`ors_up_cli` boots ORS on the state's **buffered** extract (`<state>-buffered.osm.pbf`). That extract must already exist — `ors_up_cli` exits with an error if it doesn't, so build it first with `python3 run.py build_buffered_extract_cli <state>` (the `generate_driving_distances_cli` orchestrator does this automatically). It then spawns the ORS container and waits for the health endpoint.

### Building the matrix inside the container

With ORS already running (started by hand as above), build the driving distances **from inside the dev container** — a VS Code terminal in the container, or `docker compose -f .devcontainer/docker-compose.yml run --rm app bash`:

```bash
python3 run.py generate_driving_distances_cli \
  -l datasets/configs/<config_set>/<config>.yaml
```

`run.py` works inside the container too: it detects it is containerized and runs the matrix step directly, **without** the host-side ORS orchestration — so it won't try to start or stop ORS; it just uses the instance you brought up by hand. No `--server` flag is needed either: the container is preconfigured with `ORS_URL=http://ors:8082/ors/v2/matrix/driving-car` and shares a Docker network with the ORS container, so it reaches ORS by service name. (ORS listens on `8082` internally; the `localhost:8080` default noted below applies on the **host**, where compose publishes `8080 -> 8082`.) This is also why `ors_up_cli` / `ors_down_cli` stay host-only.

### Switching states

ORS loads one extract per container. Each state has its own bind-mounted
graph cache directory under `datasets/ors_graphs/<state>-buffered/`, so switching
states is just:

```bash
python3 run.py ors_down_cli
python3 run.py build_buffered_extract_cli texas   # builds texas-buffered.osm.pbf if missing
python3 run.py ors_up_cli texas
```

ORS sees the new state's empty (or pre-built) cache directory and rebuilds
the graph automatically — no manual purge step.

To force a clean rebuild for a specific state (e.g., after refreshing the
extract), delete that state's cache directory manually:

```bash
rm -rf datasets/ors_graphs/georgia-buffered
```

### Resource budget

The first driving run for a state downloads a one-time ~13 GB US OpenStreetMap extract and builds a state+50 km buffer graph. Large border states (Texas; the 8-neighbor states) may need `ORS_XMX=16g` (or more) and a matching Docker Desktop memory limit.

Set `ORS_XMX` in your shell **before** the run — the syntax is shell-specific, and on Windows it must be a separate command first:
- macOS / Linux / WSL (bash/zsh): inline it — `ORS_XMX=16g python3 run.py generate_driving_distances_cli -l ...` — or `export ORS_XMX=16g` once for the session.
- Windows PowerShell: `$env:ORS_XMX = "16g"`, then run the command on the next line.
- Windows cmd: `set ORS_XMX=16g`, then run the command on the next line.

(The same per-shell pattern applies to any env var, e.g. `ORS_URL`.)

Once a state's graph is loaded, ORS uses ~3–5 GB of RAM. The dev container also runs solver/Python workloads. **Bump Docker Desktop's memory to ≥ 12 GB if you run both at once** — the default 8 GB is too tight.

### Where to override the ORS endpoint

The driving CLI defaults to `http://localhost:8080/ors/v2/matrix/driving-car`. Overrides, in precedence order:
- CLI flag: `--server http://...` on `generate_driving_distances_cli`.
- Env var: `ORS_URL=http://...`.

The `ors_up_cli` and `ors_down_cli` commands are **host-only** — they need access to the host's Docker daemon. From inside the dev container they refuse with a clear message. `generate_driving_distances_cli` from the host auto-orchestrates the lifecycle (so the `ors_up_cli`/`ors_down_cli` calls happen for you); from inside the container it only speaks HTTP and assumes ORS is already running.

### Migration from earlier setup

If you previously ran the older `ors_setup_cli --state X` / `ors_up_cli` workflow, your `.pbf` files lived under `.devcontainer/ors_data/`. The data directory has moved to `datasets/openrouteservice/` — one-time fix:

```bash
mv .devcontainer/ors_data/*.osm.pbf datasets/openrouteservice/
```

(This migration note can be deleted once everyone with prior installs has migrated.)

