# Equitable-Polling-Locations-Refactor

## Formatting

The following should be run before pushing any code:

- `ruff check --fix`
- `ruff format`

## CLI Operation

To run against a single config file:
`equitable_locations run-file untracked/test_config/Gwinnett_config_no_bg_school_church.yaml`

## Example Config

```yaml
# Constants for the optimization function
location: Gwinnett_GA
year:
  - "2020"
  - "2022"
bad_types:
  - "EV_2022_cease"
  - "Elec Day School - Potential"
  - "Elec Day Church - Potential"
  - "bg_centroid"
beta: -2
time_limit: 360000 #100 hours minutes
capacity: 5
relative_partner_data_file_path: Gwinnett_GA_locations_only.csv

####Optional#####
precincts_open: 12
max_min_mult: 5 #scalar >= 1
maxpctnew: 1 # in interval [0,1]
minpctold: .8 # in interval [0,1]

```

## Manual interaction with docker

```bash

docker run -ti --rm \
-v ./logs:/app/logs \
-v ./untracked:/app/untracked \
equitable_locations \
bash

```

In the container:

```bash
python untracked/optimization_examples.py
```

## TODO

- Click interface to running common commands
- litestar api to trigger same commands as click interface
- docker container containing scip install and repo code
- untracked cache folder for
  - OSM/mapping data
    - routes
    - isochrone
    - shapefiles
    - networks
  - census shapefiles
  - census demographic data
- Common functions
  - I/O
    - download/load from cache for census data
    - download/load from cache for osm data
    - download/load from cache for isochrone data
  - Schemas
    - polling site
    - origin/destination row for optimizer
  - Map Figures
    - Create base layer: County with blocks/block groups
    - Polling location layer
    - isochrone layer
  - Map data
    - generate isochrone (OSM)
- Containerization
  - Multi-layer build with poetry
  - install SCIP optimizer
  - figure out how to incorporate R

Figure examples needed:

- all isochrones within county
- 
