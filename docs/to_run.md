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

## Census API Key

The model needs a free [census API key](https://api.census.gov/data/key_signup.html) whenever it has to pull demographics or TIGER shapefiles for a county that isn't already in `datasets/census/`. If you're only re-running an existing config against data that's already on disk (or in the database), you can skip this section.

Store your key with `run.py` (one-time, interactive prompt — no external Python packages required):

```bash
python run.py set_census_key
```

This saves the key to `authentication_files/credentials.json` (gitignored). Subsequent runs pick it up automatically.

**Alternative — environment variable.** Export `CENSUS_API_KEY` instead — it takes precedence over `credentials.json` and is useful inside containers and CI:
```bash
export CENSUS_API_KEY=your-key-here
python run.py pull_census_data_cli TX "Tarrant County" 2020
```

See [Input Data — Census Data](input_files.md#census-data-demographics-and-shapefiles) for the full list of files pulled, and [Installation — Census API Key](to_install.md#census-api-key-optional-for-new-counties) for the same setup summarized from the install flow.

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

The solver consumes driving-distance CSVs at `datasets/driving/<Loc>_<ST>/<Loc>_<ST>_driving_distances.csv`. The `generate_driving_distances_cli` script builds those CSVs from existing project data (TIGER block centroids + the `<Loc>_<ST>_potential_locations.csv` already used by the solver) by routing every origin × destination pair through a locally-hosted OpenRouteService (ORS) container.

### One-time setup per state

```
python run.py ors_setup_cli --state GA
```

Downloads `georgia-latest.osm.pbf` (~50–500 MB depending on state) to `.devcontainer/ors_data/`. Pass `--force` to re-download.

### Bring ORS up, generate, bring it down

```
python run.py ors_up_cli
python run.py generate_driving_distances_cli -l datasets/configs/Gwinnett_GA/<config>.yaml
python run.py ors_down_cli
```

`ors_up_cli` polls the ORS health endpoint until ready. Graph build for a state-sized extract takes 5–10 minutes on first boot, then ~10 seconds on subsequent boots because the graph persists in a named volume. `ors_down_cli --purge-graphs` removes the cached graph too — use it when you've swapped in a new state's `.pbf` and want a clean rebuild.

### Resource budget

ORS uses ~3–5 GB of RAM once a state's graph is loaded. The dev container also runs solver/Python workloads. **Bump Docker Desktop's memory to ≥ 12 GB if you run both at once** — the default 8 GB is too tight.

### Where to override the ORS endpoint

The driving CLI defaults to `http://localhost:8080/ors/v2/matrix/driving-car`. Overrides, in precedence order:
- CLI flag: `--server http://...` on `generate_driving_distances_cli`.
- Env var: `ORS_URL=http://...`.

The `ors_setup_cli`, `ors_up_cli`, and `ors_down_cli` commands are **host-only** — they need access to the host's Docker daemon. From inside the dev container they refuse with a clear message. `generate_driving_distances_cli` itself only speaks HTTP and runs fine from either side.

