'''Tests for python/scripts/analyze_detour_ratios_cli.py.'''
import pandas as pd

from python.scripts.analyze_detour_ratios_cli import main


def _write_driving_csv(tmp_path):
    df = pd.DataFrame({
        'id_orig': ['A', 'B'],
        'id_dest': ['X', 'Y'],
        'distance_m': [200000.0, 5000.0],
        'orig_lat': [33.0, 33.0],
        'orig_lon': [-84.0, -84.0],
        'dest_lat': [34.0, 34.0],
        'dest_lon': [-84.0, -84.0],
        'source': ['driving distance', 'driving distance'],
    })
    path = tmp_path / 'county_distances_2020.csv'
    df.to_csv(path, index=True)
    return str(path)


def test_cli_prints_summary(tmp_path, capsys):
    path = _write_driving_csv(tmp_path)
    exit_code = main([path])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert 'count' in out
    assert path in out


def test_cli_writes_out_csv(tmp_path):
    path = _write_driving_csv(tmp_path)
    out_path = tmp_path / 'ratios.csv'
    main([path, '--out', str(out_path)])
    written = pd.read_csv(out_path)
    assert set(['file', 'id_orig', 'id_dest', 'distance_m', 'ratio']).issubset(written.columns)
    assert written.shape[0] == 2
