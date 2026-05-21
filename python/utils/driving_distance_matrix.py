'''Orchestrate the building of a driving-distance matrix via ORS.

This module batches ORS matrix calls, retries individual sources via the
directions endpoint when a batch fails, snaps origins that cannot be routed
to nearest haversine neighbors, and reshapes the ORS response into the
project's canonical long-form CSV shape.

External callers should use ``build_distance_matrix``. The other functions
are exposed for testing and for ad-hoc reuse.
'''
import time

import pandas as pd
from haversine import haversine, Unit

from python.utils.ors_client import OrsMatrixError, query_directions, query_matrix
from python.utils.ors_url import directions_url_from_matrix_url


HAVERSINE_SNAP_RADIUS_METERS = 1000
MATRIX_CELL_LIMIT = 2500          # Below ORS's 3500 hard cap, with margin.
MAX_SOURCES_PER_BATCH = 10        # Conservative even for small destination sets.
PER_SOURCE_RETRY_SLEEP_S = 0.1


def get_missing_origins(df: pd.DataFrame) -> set:
    '''Return the set of origin ids that have any null driving distance.

    Args:
        df: A DataFrame with columns ``id_orig`` and ``distance_m``.

    Returns:
        A set of ``id_orig`` values whose ``distance_m`` is null for at least
        one destination.
    '''
    missing_rows = df[pd.isnull(df['distance_m'])]
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
    source, compute ``distance_m + distance_to_mid`` (haversine offset from
    ``origin`` to that source). Take the minimum over those candidates.

    Args:
        origin: The id of the origin to estimate distances for.
        df: A DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``
            of already-known driving distances.
        locations: Mapping from id to ``[longitude, latitude]``.

    Returns:
        A DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``,
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
        return in_range[['id_orig', 'id_dest', 'distance_m']]

    in_range['estimated_m'] = in_range['distance_m'] + in_range['distance_to_mid']
    best = (in_range
            .sort_values('estimated_m')
            .groupby(['id_orig', 'id_dest'])
            .first()
            .reset_index())
    best['distance_m'] = best['estimated_m']
    return best[['id_orig', 'id_dest', 'distance_m']]


def _build_locations_payload(locations, source_ids, dest_ids):
    '''Return ``(loc_coords, source_indices, dest_indices)`` for the ORS body.

    Args:
        locations: Mapping from id to ``[longitude, latitude]``.
        source_ids: Iterable of origin ids in this batch.
        dest_ids: Iterable of destination ids.

    Returns:
        A tuple ``(coords, source_indices, dest_indices)`` ready to hand to
        ``query_matrix``.

    Raises:
        ValueError: When an id is missing from ``locations``.
    '''
    coords = []
    source_indices = []
    for index, source in enumerate(source_ids):
        coord = locations.get(source)
        if coord is None:
            raise ValueError(f"Source id '{source}' not found in locations")
        coords.append(coord)
        source_indices.append(index)

    offset = len(source_ids)
    dest_indices = []
    for index, dest in enumerate(dest_ids):
        coord = locations.get(dest)
        if coord is None:
            raise ValueError(f"Destination id '{dest}' not found in locations")
        coords.append(coord)
        dest_indices.append(index + offset)

    return coords, source_indices, dest_indices


def _batch_size(num_dests: int) -> int:
    '''Return the number of sources per matrix call given destination count.

    Args:
        num_dests: Number of destination ids in the request.

    Returns:
        A positive integer batch size respecting ``MATRIX_CELL_LIMIT`` and
        ``MAX_SOURCES_PER_BATCH``.
    '''
    if num_dests <= 0:
        return MAX_SOURCES_PER_BATCH
    return max(1, min(MATRIX_CELL_LIMIT // num_dests - 1, MAX_SOURCES_PER_BATCH))


def _fetch_one_batch(locations, source_batch, dest_ids, matrix_url):
    '''Fetch one source-batch via the matrix endpoint, return a long-form DataFrame.

    Args:
        locations: Mapping from id to ``[longitude, latitude]``.
        source_batch: Iterable of origin ids in this batch.
        dest_ids: Iterable of destination ids.
        matrix_url: ORS matrix endpoint URL.

    Returns:
        A long-form DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``.
    '''
    coords, source_indices, dest_indices = _build_locations_payload(
        locations, source_batch, dest_ids,
    )
    distances = query_matrix(coords, source_indices, dest_indices, matrix_url)
    return matrix_response_to_long_df(source_batch, dest_ids, distances)


def _retry_sources_individually(failed_sources, dest_ids, locations, matrix_url):
    '''For each failed source, query each destination via the directions endpoint.

    Args:
        failed_sources: Iterable of origin ids whose batch failed.
        dest_ids: Iterable of destination ids.
        locations: Mapping from id to ``[longitude, latitude]``.
        matrix_url: ORS matrix endpoint URL (used to derive the directions URL).

    Returns:
        A long-form DataFrame of successful single-pair queries.
    '''
    directions_url = directions_url_from_matrix_url(matrix_url)
    rows = []
    for source in failed_sources:
        time.sleep(PER_SOURCE_RETRY_SLEEP_S)
        for dest in dest_ids:
            try:
                distance = query_directions(locations[source], locations[dest], directions_url)
            except (ConnectionError, ValueError, KeyError, IndexError):
                continue
            if distance is not None:
                rows.append({'id_orig': source, 'id_dest': dest, 'distance_m': distance})
    return pd.DataFrame(rows, columns=['id_orig', 'id_dest', 'distance_m'])


def _snap_unroutable_origins(df, source_ids, locations):
    '''Replace null rows for unroutable origins with snapped haversine estimates.

    Args:
        df: Long-form driving-distance DataFrame with column ``distance_m``.
        source_ids: All requested origin ids.
        locations: Mapping from id to ``[longitude, latitude]``.

    Returns:
        A new DataFrame with nulls dropped and snapped rows appended for any
        origin ORS could not route.
    '''
    if df.empty:
        null_origins = set()
        routed_origins = set()
    else:
        null_origins = get_missing_origins(df)
        routed_origins = set(df.loc[~pd.isnull(df['distance_m']), 'id_orig'])
    missing = null_origins | (set(source_ids) - routed_origins)
    if not missing:
        return df

    df = df.dropna(subset=['distance_m'])
    if df.empty:
        return pd.DataFrame(columns=['id_orig', 'id_dest', 'distance_m'])

    snapped_parts = [estimate_origin(origin, df, locations) for origin in missing]
    snapped = pd.concat(snapped_parts, ignore_index=True) if snapped_parts else pd.DataFrame(
        columns=['id_orig', 'id_dest', 'distance_m'],
    )
    return pd.concat([df, snapped], ignore_index=True)


def build_distance_matrix(*, locations, source_ids, dest_ids, matrix_url) -> pd.DataFrame:
    '''Build a long-form driving-distance DataFrame for every source x dest pair.

    Strategy:
        1. Batch sources into ORS matrix calls capped at ``MATRIX_CELL_LIMIT``
           cells (sources x dests).
        2. On batch failure (``OrsMatrixError``), defer the entire batch to
           per-source single-pair retries via the directions endpoint.
        3. Origins ORS cannot route at all are snapped to their nearest
           in-range haversine neighbor via ``estimate_origin``.

    Args:
        locations: Mapping from id to ``[longitude, latitude]``.
        source_ids: Iterable of origin ids.
        dest_ids: Iterable of destination ids.
        matrix_url: ORS matrix endpoint URL.

    Returns:
        A long-form DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``.
    '''
    source_ids = list(dict.fromkeys(source_ids))   # Dedup, preserve order.
    dest_ids = list(dict.fromkeys(dest_ids))

    batch_size = _batch_size(len(dest_ids))
    failed_sources = []
    batch_dfs = []
    for start in range(0, len(source_ids), batch_size):
        source_batch = source_ids[start:start + batch_size]
        try:
            batch_dfs.append(_fetch_one_batch(locations, source_batch, dest_ids, matrix_url))
        except OrsMatrixError:
            failed_sources.extend(source_batch)

    df = pd.concat(batch_dfs, ignore_index=True) if batch_dfs else pd.DataFrame(
        columns=['id_orig', 'id_dest', 'distance_m'],
    )

    if failed_sources:
        retry_df = _retry_sources_individually(failed_sources, dest_ids, locations, matrix_url)
        df = pd.concat([df, retry_df], ignore_index=True)

    return _snap_unroutable_origins(df, source_ids, locations)


def resume_from_partial_output(output_path, source_ids, dest_ids):
    '''Return ``(existing_df, remaining_pairs)`` for resuming a partial run.

    Fixes the upstream geolib bug where an existing partial output caused the
    CLI to return without writing anything. Instead, treat the existing file
    as a warm-start cache and compute the pairs still to fetch.

    Args:
        output_path: Path to a possibly-existing CSV with columns
            ``id_orig``, ``id_dest``, ``distance_m``.
        source_ids: All requested origin ids.
        dest_ids: All requested destination ids.

    Returns:
        A tuple ``(existing_df, remaining_pairs)`` where ``existing_df`` is the
        loaded DataFrame (empty if the file is missing) and ``remaining_pairs``
        is a list of ``(id_orig, id_dest)`` tuples not yet present in the file.
    '''
    try:
        existing_df = pd.read_csv(output_path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        existing_df = pd.DataFrame(columns=['id_orig', 'id_dest', 'distance_m'])

    present = set(zip(existing_df.get('id_orig', []), existing_df.get('id_dest', [])))
    all_pairs = [(s, d) for s in source_ids for d in dest_ids]
    remaining = [pair for pair in all_pairs if pair not in present]
    return existing_df, remaining
