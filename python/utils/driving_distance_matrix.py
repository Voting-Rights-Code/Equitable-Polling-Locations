'''Orchestrate the building of a driving-distance matrix via ORS.

This module contains the batching and retry-on-failure protocols. 
Batching and retries occur by source, not destination, for three reasons:
there are more sources than destinations; sources are census block
centroids that may not sit on a road; and destinations are already
real, road-valid addresses. Each failed source is retried one
origin/destination pair at a time. Furthermore, it drops unroutable
rows, to avoid silent passing of these errors downstream. Finally,
it reshapes the response to the desired long-form output.


External callers should use ``build_distance_matrix``. The other functions
are exposed for testing and for ad-hoc reuse.
'''
import time
from typing import TextIO

import pandas as pd
import requests

from python.solver.constants import (
    DISTANCE_DISTANCE_M, DISTANCE_ID_DEST, DISTANCE_ID_ORIG,
)
from python.utils.ors_client import OrsMatrixError, query_directions, query_matrix
from python.utils.ors_url import directions_url_from_matrix_url


MATRIX_CELL_LIMIT = 2500          # Below ORS's 3500 hard cap, with margin.
MAX_SOURCES_PER_BATCH = 10        # Conservative even for small destination sets.
PER_SOURCE_RETRY_SLEEP_S = 0.1

# Verbosity level constants. The integers 0/1/2 are the public contract
# (set by argparse 'count' in the CLI); these names are internal.
_LEVEL_DEFAULT = 0
_LEVEL_V = 1
_LEVEL_VV = 2

def _emit(message: str, level: int, log_fh: TextIO, verbosity: int) -> None:
    '''Write to ``log_fh`` always; to stdout only if ``level <= verbosity``.

    Args:
        message: The string to emit.
        level: The minimum verbosity required for the message to appear on screen.
            ``_LEVEL_DEFAULT`` (0) is always on screen; ``_LEVEL_V`` (1) needs ``-v``;
            ``_LEVEL_VV`` (2) needs ``-vv``.
        log_fh: Open writable text file handle. The message is always written here,
            regardless of verbosity, then flushed.
        verbosity: Caller's verbosity ceiling. The CLI sets this from ``args.verbose``.
    '''
    log_fh.write(message + '\n')
    log_fh.flush()
    if level <= verbosity:
        print(message)


def get_origins_with_blank_distances(df: pd.DataFrame) -> set:
    '''Return the set of origin ids that have any null driving distance.

    Args:
        df: A DataFrame with columns ``id_orig`` and ``distance_m``.

    Returns:
        A set of ``id_orig`` values whose ``distance_m`` is null for at least
        one destination.
    '''
    missing_rows = df[pd.isnull(df[DISTANCE_DISTANCE_M])]
    return set(missing_rows[DISTANCE_ID_ORIG])


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
            rows.append({
                DISTANCE_ID_ORIG: source,
                DISTANCE_ID_DEST: dest,
                DISTANCE_DISTANCE_M: distance_m,
            })
    return pd.DataFrame(
        rows,
        columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M],
    )


def _reject_negative_distances(df: pd.DataFrame) -> None:
    '''Raise if any ``distance_m`` is negative.

    Guards against a negative driving distance appearing in the data matrix, 
    which is a documented feature of some ORS versions. A "no route" response 
    from ORS, represented as null (NaN), and a 0 distance are both kept.

    Args:
        df: Long-form DataFrame with a ``distance_m`` column.

    Raises:
        ValueError: If any row has a negative ``distance_m``.
    '''
    negative_mask = df[DISTANCE_DISTANCE_M] < 0
    if negative_mask.any():
        offender = df[negative_mask].iloc[0]
        raise ValueError(
            f'{int(negative_mask.sum())} routed pair(s) have a negative distance_m, '
            f'which is never a valid driving distance (first: '
            f'{offender[DISTANCE_ID_ORIG]} -> {offender[DISTANCE_ID_DEST]}, '
            f'distance_m={offender[DISTANCE_DISTANCE_M]}). A negative value signals '
            f'a routing-backend error; regenerate the driving matrix.'
        )


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


def _retry_sources_individually(failed_sources: list[str],
                                dest_ids: list[str],
                                locations: dict[str, list[float]],
                                matrix_url: str,
                                *,
                                log_fh: TextIO,
                                verbosity: int) -> pd.DataFrame:
    '''For each failed source, query each destination via the directions endpoint.

    Returns a long-form DataFrame of successful single-pair queries.

    Args:
        failed_sources: Origin ids whose matrix batch failed; each is retried per-dest.
        dest_ids: All destination ids to query for each failed source.
        locations: Mapping from id to ``[longitude, latitude]``.
        matrix_url: Matrix URL — the directions URL is derived from it.
        log_fh: Open writable text file handle. Retry events are always written here.
        verbosity: Screen-output ceiling. Retry events emit at ``_LEVEL_VV`` so they
            require ``-vv`` to appear on screen.
    '''
    directions_url = directions_url_from_matrix_url(matrix_url)
    rows = []
    for source in failed_sources:
        _emit(f'retrying source {source} via directions endpoint',
              _LEVEL_VV, log_fh, verbosity)
        time.sleep(PER_SOURCE_RETRY_SLEEP_S)
        for dest in dest_ids:
            try:
                distance = query_directions(locations[source], locations[dest], directions_url)
            except requests.exceptions.RequestException:
                _emit(f'directions raised for {source} -> {dest}: skipping',
                      _LEVEL_VV, log_fh, verbosity)
                continue
            if distance is None:
                _emit(f'directions returned None for {source} -> {dest}: skipping',
                      _LEVEL_VV, log_fh, verbosity)
                continue
            rows.append({
                DISTANCE_ID_ORIG: source,
                DISTANCE_ID_DEST: dest,
                DISTANCE_DISTANCE_M: distance,
            })
    return pd.DataFrame(
        rows,
        columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M],
    )


def build_distance_matrix(*,
                          locations: dict[str, list[float]],
                          source_ids: list[str],
                          dest_ids: list[str],
                          matrix_url: str,
                          log_fh: TextIO,
                          verbosity: int = 0) -> pd.DataFrame:
    '''Build a long-form driving-distance DataFrame for every routable source x dest pair.

    Strategy:
        1. Batch sources into ORS matrix calls capped at ``MATRIX_CELL_LIMIT``
           cells (sources x dests).
        2. On batch failure (``OrsMatrixError``), defer the entire batch to
           per-source single-pair retries via the directions endpoint.
        3. A pair ORS cannot route is dropped. This function does not raise or 
        fail on a drop — the CLI compares requested source_ids against returned 
        id_orig values and fails on any gap. see #338


    Args:
        locations: Mapping from id to ``[longitude, latitude]``.
        source_ids: Iterable of origin ids.
        dest_ids: Iterable of destination ids.
        matrix_url: ORS matrix endpoint URL.
        log_fh: Open writable text file handle for the run log. Per-batch progress
            and retry detail are written here regardless of verbosity.
        verbosity: Screen-output ceiling (0 = quiet default, 1 = ``-v``, 2 = ``-vv``).

    Returns:
        A long-form DataFrame with columns ``id_orig``, ``id_dest``,
        ``distance_m``, holding only successfully routed pairs.

    Raises:
        ValueError: If the routing backend returns a negative distance.
    '''
    source_ids = list(dict.fromkeys(source_ids))   # Dedup, preserve order.
    dest_ids = list(dict.fromkeys(dest_ids))

    #run batches and concatenate
    batch_size = _batch_size(len(dest_ids))
    failed_sources = []
    batch_dfs = []
    for start in range(0, len(source_ids), batch_size):
        batch_start = time.monotonic()
        source_batch = source_ids[start:start + batch_size]
        try:
            batch_dfs.append(_fetch_one_batch(locations, source_batch, dest_ids, matrix_url))
        except OrsMatrixError:
            failed_sources.extend(source_batch)
        elapsed = time.monotonic() - batch_start
        done = min(start + batch_size, len(source_ids))
        _emit(f'{done}/{len(source_ids)}: {elapsed:.2f}s', _LEVEL_V, log_fh, verbosity)

    df = pd.concat(batch_dfs, ignore_index=True) if batch_dfs else pd.DataFrame(
        columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M],
    )

    #retry failed sources and concatenate
    if failed_sources:
        retry_df = _retry_sources_individually(
            failed_sources, dest_ids, locations, matrix_url,
            log_fh=log_fh, verbosity=verbosity,
        )
        df = pd.concat([df, retry_df], ignore_index=True)

    # Fail loud on negative distances
    _reject_negative_distances(df)

    # Drop null (no-route) rows
    return df.dropna(subset=[DISTANCE_DISTANCE_M]).reset_index(drop=True)


def identify_unmatched_pairs(output_path, source_ids, dest_ids):
    '''Load an existing driving-distance CSV, if one exists, and identify the 
    (id_orig, id_dest) pairs from source_ids/dest_ids not yet present in it. 
    Presence is decided by the id columns only — a row with a blank
    distance_m still counts as present. Runs before the CLI queries ORS for the remaining pairs.

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
        # Force the id columns to str: numeric-looking GEOIDs otherwise load as
        # int64, so the present-pair check below (and the CLI's later
        # drop_duplicates) never match the str source/dest ids. See #305.
        existing_df = pd.read_csv(
            output_path,
            dtype={DISTANCE_ID_ORIG: str, DISTANCE_ID_DEST: str},
        )
    except (FileNotFoundError, pd.errors.EmptyDataError):
        existing_df = pd.DataFrame(
            columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M],
        )

    present = set(zip(
        existing_df.get(DISTANCE_ID_ORIG, []),
        existing_df.get(DISTANCE_ID_DEST, []),
    ))
    all_pairs = [(s, d) for s in source_ids for d in dest_ids]
    remaining = [pair for pair in all_pairs if pair not in present]
    return existing_df, remaining
