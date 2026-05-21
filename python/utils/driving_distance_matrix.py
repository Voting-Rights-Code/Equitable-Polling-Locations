'''Orchestrate the building of a driving-distance matrix via ORS.

This module batches ORS matrix calls, retries individual sources via the
directions endpoint when a batch fails, snaps origins that cannot be routed
to nearest haversine neighbors, and reshapes the ORS response into the
project's canonical long-form CSV shape.

External callers should use ``build_distance_matrix``. The other functions
are exposed for testing and for ad-hoc reuse.
'''
import pandas as pd
from haversine import haversine, Unit


HAVERSINE_SNAP_RADIUS_METERS = 1000


def get_missing_origins(df: pd.DataFrame) -> set:
    '''Return the set of origin ids that have any null driving distance.

    Args:
        df: A DataFrame with columns ``id_orig`` and ``driving_m``.

    Returns:
        A set of ``id_orig`` values whose ``driving_m`` is null for at least
        one destination.
    '''
    missing_rows = df[pd.isnull(df['driving_m'])]
    return set(missing_rows['id_orig'])


def matrix_response_to_long_df(source_names, dest_names, distances) -> pd.DataFrame:
    '''Reshape an ORS matrix response into a long ``(id_orig, id_dest, distance_m)`` frame.

    Args:
        source_names: Row labels (one per origin).
        dest_names: Column labels (one per destination).
        distances: ``distances[i][j]`` is the distance from ``source_names[i]``
            to ``dest_names[j]``, as returned by ORS.

    Returns:
        A long-form DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``.
    '''
    rows = []
    for source, source_row in zip(source_names, distances):
        for dest, distance_m in zip(dest_names, source_row):
            rows.append({'id_orig': source, 'id_dest': dest, 'distance_m': distance_m})
    return pd.DataFrame(rows, columns=['id_orig', 'id_dest', 'distance_m'])


def estimate_origin(origin: str, df: pd.DataFrame, locations: dict) -> pd.DataFrame:
    '''Estimate distances for an unroutable origin by snapping to a nearby neighbor.

    For each destination, look at all known sources within
    ``HAVERSINE_SNAP_RADIUS_METERS`` haversine of ``origin``. For each such
    source, compute ``driving_m + distance_to_mid`` (haversine offset from
    ``origin`` to that source). Take the minimum over those candidates.

    Args:
        origin: The id of the origin to estimate distances for.
        df: A DataFrame with columns ``id_orig``, ``id_dest``, ``driving_m``
            of already-known driving distances.
        locations: Mapping from id to ``[longitude, latitude]``.

    Returns:
        A DataFrame with columns ``id_orig``, ``id_dest``, ``driving_m``,
        holding the best snapped estimate per destination. Empty if no
        in-range neighbor exists.
    '''
    candidates = df.rename(columns={'id_orig': 'midpoint'}).copy()
    candidates['id_orig'] = origin

    origin_latlon = tuple(reversed(locations[origin]))
    candidates['distance_to_mid'] = candidates['midpoint'].apply(
        lambda mid: haversine(origin_latlon, tuple(reversed(locations[mid])), unit=Unit.METERS)
    )

    in_range = candidates[candidates['distance_to_mid'] < HAVERSINE_SNAP_RADIUS_METERS].copy()
    if in_range.empty:
        return in_range[['id_orig', 'id_dest', 'driving_m']]

    in_range['estimated_m'] = in_range['driving_m'] + in_range['distance_to_mid']
    best = (in_range
            .sort_values('estimated_m')
            .groupby(['id_orig', 'id_dest'])
            .first()
            .reset_index())
    best = best.rename(columns={'estimated_m': 'driving_m_snapped'})
    best['driving_m'] = best['driving_m_snapped']
    return best[['id_orig', 'id_dest', 'driving_m']]
