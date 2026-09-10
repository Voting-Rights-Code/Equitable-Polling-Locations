'''Detour-ratio diagnostic for cross-border distance inflation (issue #226, Phase 1).

Compares stored driving distances against a recomputed straight-line (haversine)
baseline, per (id_orig, id_dest) pair, to surface counties whose distance matrix
is silently inflated by missing cross-border roads. Distance only (distance_m);
unrelated to the driving-time metric.
'''

import os

import pandas as pd
from haversine import haversine_vector, Unit

from python.solver.constants import (
    DISTANCE_DISTANCE_M,
    DISTANCE_ORIG_LAT, DISTANCE_ORIG_LON,
    DISTANCE_DEST_LAT, DISTANCE_DEST_LON,
    DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_SOURCE,
    DISTANCE_SOURCE_DRIVING_DISTANCE,
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


def summarize_detour_ratios(
    ratios: pd.Series,
    thresholds: tuple[float, ...] = (1.5, 2.0, 3.0),
) -> dict[str, float]:
    '''Summarize a distribution of detour ratios.

    Args:
        ratios: Per-pair driving/haversine ratios; NaNs (e.g. coincident
            points) are ignored.
        thresholds: Ratio cut points to count exceedances at.

    Returns:
        A dict with count, median, p90/p95/p99, max, and count_over_<t> /
        frac_over_<t> for each threshold. Quantile keys are NaN when no
        finite ratios are present.
    '''
    finite = ratios.dropna()
    count = int(finite.shape[0])
    summary: dict[str, float] = {
        'count': float(count),
        'median': float(finite.median()) if count else float('nan'),
        'p90': float(finite.quantile(0.90)) if count else float('nan'),
        'p95': float(finite.quantile(0.95)) if count else float('nan'),
        'p99': float(finite.quantile(0.99)) if count else float('nan'),
        'max': float(finite.max()) if count else float('nan'),
    }
    for threshold in thresholds:
        over = int((finite > threshold).sum())
        summary[f'count_over_{threshold}'] = float(over)
        summary[f'frac_over_{threshold}'] = (over / count) if count else float('nan')
    return summary


def load_distances_csv(path: str) -> pd.DataFrame:
    '''Load a combined distances CSV produced by a driving model-data run.

    Args:
        path: Path to a ``<location>_distances_<year>.csv`` file.

    Returns:
        The DataFrame with id_orig/id_dest as strings.

    Raises:
        ValueError: If the file does not exist, or its ``source`` column
            indicates it is not a driving-distance file (which would make every
            detour ratio ~1 and the diagnostic meaningless).
    '''
    if not os.path.isfile(path):
        raise ValueError(f'Distance data file {path} does not exist.')

    distances = pd.read_csv(
        path, index_col=0,
        dtype={DISTANCE_ID_ORIG: str, DISTANCE_ID_DEST: str},
    )

    if DISTANCE_SOURCE in distances.columns:
        sources = distances[DISTANCE_SOURCE].dropna().unique()
        if not all('driving' in str(source) for source in sources):
            raise ValueError(
                f'{path} is not a driving-distance file (source={list(sources)}); '
                f'the detour-ratio diagnostic needs driving distances. '
                f'Expected source containing {DISTANCE_SOURCE_DRIVING_DISTANCE!r}.'
            )
    return distances
