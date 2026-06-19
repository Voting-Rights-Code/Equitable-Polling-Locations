import geopandas as gpd
import pytest

from python.utils.buffered_extract import build_buffer_polygon


def test_buffer_polygon_contains_and_grows_state(tmp_path, monkeypatch):
    monkeypatch.setattr('python.utils.buffered_extract.ORS_DATA_DIR', str(tmp_path))
    out_path = build_buffer_polygon('georgia', buffer_km=50)
    buffered = gpd.read_file(out_path)
    states = gpd.read_file('datasets/boundaries/us_states.geojson')
    georgia = states[states['postal'] == 'GA'].to_crs(buffered.crs)
    # Buffered polygon strictly contains the original state outline.
    assert buffered.union_all().contains(georgia.union_all())
    # And it is materially larger (area grows by the 50 km ring).
    assert buffered.to_crs(georgia.estimate_utm_crs()).area.iloc[0] > \
        georgia.to_crs(georgia.estimate_utm_crs()).area.iloc[0]
    assert str(buffered.crs).upper().endswith('4326')


def test_buffer_polygon_unknown_slug_raises(tmp_path, monkeypatch):
    monkeypatch.setattr('python.utils.buffered_extract.ORS_DATA_DIR', str(tmp_path))
    with pytest.raises(ValueError):
        build_buffer_polygon('atlantis')
