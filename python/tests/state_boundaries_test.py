"""Tests for the committed datasets/boundaries/us_states.geojson artifact."""
import geopandas as gpd

from python.utils.ors_setup import STATE_CODE_TO_SLUG

BOUNDARY_PATH = 'datasets/boundaries/us_states.geojson'


def test_boundary_file_has_all_states_with_postal() -> None:
    """Boundary file contains exactly the 50 states + DC with a postal column in EPSG:4326."""
    states = gpd.read_file(BOUNDARY_PATH)
    assert 'postal' in states.columns
    postals = set(states['postal'])
    assert postals == set(STATE_CODE_TO_SLUG.keys())  # 50 states + DC, exact match
    assert str(states.crs).upper().endswith('4326')
