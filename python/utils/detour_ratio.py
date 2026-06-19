'''Detour-ratio diagnostic for cross-border distance inflation (issue #226, Phase 1).

Compares stored driving distances against a recomputed straight-line (haversine)
baseline, per (id_orig, id_dest) pair, to surface counties whose distance matrix
is silently inflated by missing cross-border roads. Distance only (distance_m);
unrelated to the driving-time metric.
'''

import pandas as pd
from haversine import haversine_vector, Unit

from python.solver.constants import (
    DISTANCE_DISTANCE_M,
    DISTANCE_ORIG_LAT, DISTANCE_ORIG_LON,
    DISTANCE_DEST_LAT, DISTANCE_DEST_LON,
)

_REQUIRED_RATIO_COLUMNS = (
    DISTANCE_DISTANCE_M,
    DISTANCE_ORIG_LAT, DISTANCE_ORIG_LON,
    DISTANCE_DEST_LAT, DISTANCE_DEST_LON,
)


def compute_detour_ratios(distances: pd.DataFrame) -> pd.Series:
    '''Compute the driving-to-haversine distance ratio for each row.

    The haversine baseline is recomputed from the origin/destination lat/lon
    columns with the same `haversine` library the solver uses, so the ratio is
    apples-to-apples with the model's own straight-line distances.

    Args:
        distances: DataFrame with DISTANCE_DISTANCE_M (driving meters) and the
            four lat/lon columns (orig_lat, orig_lon, dest_lat, dest_lon).

    Returns:
        A float Series aligned to ``distances.index`` holding
        ``distance_m / haversine_m``; rows whose recomputed haversine distance
        is 0 (coincident points) are NaN.

    Raises:
        ValueError: If any required column is missing.
    '''
    missing = [column for column in _REQUIRED_RATIO_COLUMNS if column not in distances.columns]
    if missing:
        raise ValueError(f'Distance data is missing required columns: {missing}')

    origins = list(zip(distances[DISTANCE_ORIG_LAT], distances[DISTANCE_ORIG_LON]))
    destinations = list(zip(distances[DISTANCE_DEST_LAT], distances[DISTANCE_DEST_LON]))
    haversine_m = pd.Series(
        haversine_vector(origins, destinations, unit=Unit.METERS),
        index=distances.index,
    )

    ratios = distances[DISTANCE_DISTANCE_M] / haversine_m
    ratios[haversine_m == 0] = float('nan')
    return ratios
