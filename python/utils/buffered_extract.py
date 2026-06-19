'''Build a state-plus-buffer OSM extract for cross-border-correct routing (#226).

Runs IN-CONTAINER (imports geopandas and shells out to osmium). Produces a
`<state>-buffered.osm.pbf` clipped from a cached full-US source using a 50 km
buffer polygon around the state boundary. Driving distance only.
'''

import os

import geopandas as gpd

from python.utils.ors_setup import (
    GEOFABRIK_STATE_SLUGS, STATE_CODE_TO_SLUG, ORS_DATA_DIR,
    buffer_polygon_path,
)

DEFAULT_BOUNDARY_PATH = 'datasets/boundaries/us_states.geojson'
DEFAULT_BUFFER_KM = 50
SIMPLIFY_TOLERANCE_M = 1000  # CONFIRM (Decision 2)
SLUG_TO_POSTAL = {slug: postal for postal, slug in STATE_CODE_TO_SLUG.items()}


def build_buffer_polygon(
    state_slug: str,
    buffer_km: int = DEFAULT_BUFFER_KM,
    boundary_path: str = DEFAULT_BOUNDARY_PATH,
) -> str:
    '''Write a WGS84 GeoJSON of the state outline grown by buffer_km.

    Args:
        state_slug: Geofabrik state slug (e.g. 'georgia').
        buffer_km: Buffer width in kilometres.
        boundary_path: Path to the bundled state-boundary GeoJSON.

    Returns:
        The path to the written buffer-polygon GeoJSON.

    Raises:
        ValueError: If state_slug is not a known Geofabrik state slug.
    '''
    if state_slug not in GEOFABRIK_STATE_SLUGS:
        raise ValueError(f'Unknown state slug: {state_slug!r}.')

    states = gpd.read_file(boundary_path)
    state = states[states['postal'] == SLUG_TO_POSTAL[state_slug]]

    metric = state.to_crs(state.estimate_utm_crs())
    buffered = metric.buffer(buffer_km * 1000).simplify(SIMPLIFY_TOLERANCE_M)
    out = gpd.GeoSeries(buffered, crs=metric.crs).to_crs(4326)

    os.makedirs(ORS_DATA_DIR, exist_ok=True)
    out_path = buffer_polygon_path(state_slug)
    out.to_file(out_path, driver='GeoJSON')
    return out_path
