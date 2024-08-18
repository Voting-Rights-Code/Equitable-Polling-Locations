# Equitable-Polling-Locations-Refactor

## Formatting

The following should be run before pushing any code:

- `ruff check --fix`
- `ruff format`

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
