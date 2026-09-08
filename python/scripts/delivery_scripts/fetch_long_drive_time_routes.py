"""One-off script: fetch ORS route geometries for the over-30-minute,
populated blocks in distance_flagged_blocks_20_min.csv (the `bar` table from
the R session).

Exploratory/one-off -- not wired into run.py's CLI, not covered by TDD.
Reuses existing, tested project code (derive_origins_and_destinations,
query_route_geometry) rather than re-deriving coordinates, so the fetched
routes use the exact same origin/destination points the original distance
matrix was built from.

Run from inside the devcontainer, with the ORS sibling container already up
(`python3 run.py ors_up_cli west-virginia` from the host):

    python3 -m python.scripts.delivery_scripts.fetch_long_drive_time_routes
"""
import json
import types

import pandas as pd
import requests
import yaml

from python.scripts.generate_driving_distances_cli import derive_origins_and_destinations
from python.utils.ors_client import query_route_geometry
from python.utils.ors_url import directions_url_from_matrix_url, resolve_ors_url

# ORS's single-pair GET /directions endpoint (query_route_geometry) enforces
# a fixed 400m snap-to-road radius with no override. The matrix endpoint
# (which built the original distances) tolerates snapping from further away,
# so a handful of rural block centroids that matrix-routed fine come back
# "no routable point" from the GET endpoint. The richer POST .../geojson
# endpoint accepts a radiuses override and finds the same route -- confirmed
# against block 540610114004013 (Mason Dixon Elementary School): matrix gave
# 19883.59m/1860.98s, and this retry path returns 19883.6m/1861.0s, the same
# route.
RETRY_SNAP_RADIUS_METERS = 1000

CONFIG_PATH = (
    "datasets/configs/Monongalia_County_WV_driving_original_configs/"
    "Monongalia_County_WV_metric_driving_time.yaml"
)
DISTANCE_FLAGGED_BLOCKS_CSV = (
    "precinct_analysis_outputs/Monongalia_County_WV/distance_flagged_blocks_20_min.csv"
)
OUTPUT_GEOJSON = (
    "precinct_analysis_outputs/Monongalia_County_WV/long_drive_time_routes.geojson"
)
DURATION_THRESHOLD_MIN = 30


def query_route_geometry_with_wider_radius(source, dest, directions_url, radius_m):
    """Retry a single-pair route fetch via POST .../geojson with a wider snap radius.

    Args:
        source: ``[longitude, latitude]`` origin.
        dest: ``[longitude, latitude]`` destination.
        directions_url: The GET-style directions endpoint URL (as returned by
            ``directions_url_from_matrix_url``); ``/geojson`` is appended for
            this call.
        radius_m: Snap-to-road radius, in meters, applied to both points.

    Returns:
        The route geometry as a list of ``[longitude, latitude]`` pairs, or
        ``None`` if ORS still can't find a route.
    """
    url = f"{directions_url}/geojson"
    body = {"coordinates": [source, dest], "radiuses": [radius_m, radius_m]}
    response = requests.post(url, json=body, timeout=60)
    parsed = response.json()
    if "error" in parsed:
        return None
    try:
        return parsed["features"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError):
        return None


def select_extremal_distances(csv_path: str) -> pd.DataFrame:
    """Select over-threshold, populated blocks, sorted by duration.

    id_orig was written wrapped as an Excel/Sheets formula-text literal
    (`="<geoid>"`, see force_text_for_spreadsheet() in shape_extraction_functions.r)
    so it opens as text in a spreadsheet instead of a mangled number --
    strip that back to the plain GEOID for the locations lookup here.
    """
    driving_distances = pd.read_csv(csv_path, dtype={"id_orig": str})
    driving_distances["id_orig"] = driving_distances["id_orig"].str.replace(r'^="|"$', "", regex=True)
    extremal_distances = driving_distances[
        (driving_distances["duration_min"] > DURATION_THRESHOLD_MIN) & (driving_distances["total_population"] > 0)
    ]
    return extremal_distances.sort_values("duration_min")[
        ["id_orig", "id_dest", "duration_min", "total_population"]
    ]


def load_location_and_census_year(config_path: str) -> types.SimpleNamespace:
    """Read just `location`/`census_year` from a config yaml directly.

    Workaround because the configs in this branch do not have the
    drive_time_metric field yet.
    """
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return types.SimpleNamespace(
        location=raw["location"], census_year=raw["census_year"],
    )


def driving_features(row: pd.DataFrame, directions_url, locations):
    origin = locations[row["id_orig"]]
    dest = locations[row["id_dest"]]
    coords = query_route_geometry(origin, dest, directions_url)
    if coords is None: #initial query didn't return anything, try larger radius
        coords = query_route_geometry_with_wider_radius(
            origin, dest, directions_url, RETRY_SNAP_RADIUS_METERS
        )
    if coords is None: #still nothing returned
        raise ValueError(f"no route found for {row['id_orig']} -> {row['id_dest']}")
    route_json= {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "id_orig": row["id_orig"],
                "id_dest": row["id_dest"],
                "duration_min": row["duration_min"],
                "total_population": int(row["total_population"]),
            },
        }
    return route_json


def main() -> None:
    """Fetch and save a route geometry for every row in `bar`."""
    config = load_location_and_census_year(CONFIG_PATH)
    locations, _, _ = derive_origins_and_destinations(config)

    directions_url = directions_url_from_matrix_url(resolve_ors_url())

    #get extreme distances to map
    extremal = select_extremal_distances(DISTANCE_FLAGGED_BLOCKS_CSV)

    #get fratures from ORS
    features = [driving_features(row, directions_url, locations) for
        _, row in extremal.iterrows()]

    #write to json
    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)


if __name__ == "__main__":
    main()
