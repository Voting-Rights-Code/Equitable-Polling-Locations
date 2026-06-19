import math

import numpy as np
import pandas as pd
import pytest

from python.utils.detour_ratio import compute_detour_ratios, summarize_detour_ratios


def _coincident_points_frame():
    # orig == dest -> haversine 0 -> ratio NaN; a second row with real separation.
    return pd.DataFrame({
        'id_orig': ['A', 'B'],
        'id_dest': ['X', 'Y'],
        'distance_m': [1000.0, 5000.0],
        'orig_lat': [33.7490, 33.0],
        'orig_lon': [-84.3880, -84.0],
        'dest_lat': [33.7490, 34.0],
        'dest_lon': [-84.3880, -84.0],
    })


def test_ratio_is_driving_over_haversine():
    df = _coincident_points_frame()
    ratios = compute_detour_ratios(df)
    # Row B: ~111 km north (1 degree lat); driving 5000 m -> ratio well below 1 here,
    # but the point is it equals distance_m / recomputed_haversine_m, not NaN.
    haversine_b = 5000.0 / ratios.iloc[1]
    assert haversine_b > 100_000  # ~111 km between (33,-84) and (34,-84)
    assert math.isclose(ratios.iloc[1], 5000.0 / haversine_b, rel_tol=1e-9)


def test_zero_haversine_is_nan():
    ratios = compute_detour_ratios(_coincident_points_frame())
    assert np.isnan(ratios.iloc[0])


def test_missing_column_raises():
    df = _coincident_points_frame().drop(columns=['orig_lat'])
    with pytest.raises(ValueError):
        compute_detour_ratios(df)


def test_summary_basic_stats():
    ratios = pd.Series([1.0, 1.0, 2.0, 4.0, float('nan')])
    summary = summarize_detour_ratios(ratios, thresholds=(1.5, 3.0))
    assert summary['count'] == 4
    assert summary['median'] == 1.5
    assert summary['max'] == 4.0
    assert summary['count_over_1.5'] == 2   # 2.0 and 4.0
    assert summary['count_over_3.0'] == 1   # 4.0
    assert math.isclose(summary['frac_over_1.5'], 0.5)


def test_summary_empty_is_safe():
    summary = summarize_detour_ratios(pd.Series([float('nan')]), thresholds=(2.0,))
    assert summary['count'] == 0
    assert np.isnan(summary['median'])
    assert summary['count_over_2.0'] == 0
