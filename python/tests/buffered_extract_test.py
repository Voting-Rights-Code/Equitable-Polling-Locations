'''Tests for python/utils/buffered_extract.py.'''
import geopandas as gpd
import pytest

from python.utils.buffered_extract import build_buffer_polygon, build_buffered_pbf, ensure_us_source


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


def test_ensure_us_source_skips_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr('python.utils.buffered_extract.ORS_DATA_DIR', str(tmp_path))
    target = tmp_path / 'us-latest.osm.pbf'
    target.write_bytes(b'existing')
    monkeypatch.setattr('python.utils.buffered_extract.us_source_path',
                        lambda: str(target))
    called = []
    monkeypatch.setattr('python.utils.buffered_extract.urllib.request.urlretrieve',
                        lambda url, dest: called.append(url))
    result = ensure_us_source()
    assert result == str(target)
    assert not called  # already present -> no download


def test_ensure_us_source_downloads_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr('python.utils.buffered_extract.ORS_DATA_DIR', str(tmp_path))
    target = tmp_path / 'us-latest.osm.pbf'
    monkeypatch.setattr('python.utils.buffered_extract.us_source_path',
                        lambda: str(target))

    def fake_retrieve(url, dest):
        del url
        with open(dest, 'wb') as handle:
            handle.write(b'downloaded')

    monkeypatch.setattr('python.utils.buffered_extract.urllib.request.urlretrieve',
                        fake_retrieve)
    result = ensure_us_source()
    assert result == str(target)
    assert target.read_bytes() == b'downloaded'
    assert not (tmp_path / 'us-latest.osm.pbf.partial').exists()  # atomic cleanup


def test_build_buffered_pbf_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr('python.utils.buffered_extract.ORS_DATA_DIR', str(tmp_path))
    existing = tmp_path / 'georgia-buffered.osm.pbf'
    existing.write_bytes(b'cached')
    monkeypatch.setattr('python.utils.buffered_extract.buffered_pbf_path',
                        lambda slug: str(existing))
    ran = []
    monkeypatch.setattr('python.utils.buffered_extract.subprocess.run',
                        lambda *a, **k: ran.append(a))
    assert build_buffered_pbf('georgia') == str(existing)
    assert not ran  # cached -> osmium not invoked


def test_build_buffered_pbf_invokes_osmium(tmp_path, monkeypatch):
    monkeypatch.setattr('python.utils.buffered_extract.ORS_DATA_DIR', str(tmp_path))
    out = tmp_path / 'georgia-buffered.osm.pbf'
    monkeypatch.setattr('python.utils.buffered_extract.buffered_pbf_path',
                        lambda slug: str(out))
    monkeypatch.setattr('python.utils.buffered_extract.ensure_us_source',
                        lambda: str(tmp_path / 'us-latest.osm.pbf'))
    monkeypatch.setattr('python.utils.buffered_extract.build_buffer_polygon',
                        lambda slug: str(tmp_path / 'georgia-buffer.geojson'))
    captured = {}
    monkeypatch.setattr('python.utils.buffered_extract.subprocess.run',
                        lambda cmd, **k: captured.setdefault('cmd', cmd))
    result = build_buffered_pbf('georgia')
    assert result == str(out)
    assert captured['cmd'][:2] == ['osmium', 'extract']
    assert '--polygon' in captured['cmd']
    assert str(out) in captured['cmd']
