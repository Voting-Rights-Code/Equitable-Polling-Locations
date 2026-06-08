'''Orchestrate the building of a driving-distance matrix via ORS.

This module batches ORS matrix calls, retries individual sources via the
directions endpoint when a batch fails, snaps origins that cannot be routed
to nearest haversine neighbors, and reshapes the ORS response into the
project's canonical long-form CSV shape.

External callers should use ``build_distance_matrix``. The other functions
are exposed for testing and for ad-hoc reuse.
'''
import time
from typing import TextIO

import pandas as pd
import requests
from haversine import haversine, Unit

from python.solver.constants import (
    DISTANCE_DISTANCE_M, DISTANCE_DURATION_S, DISTANCE_ID_DEST, DISTANCE_ID_ORIG,
)
from python.utils.ors_client import OrsMatrixError, query_directions, query_matrix
from python.utils.ors_url import directions_url_from_matrix_url


HAVERSINE_SNAP_RADIUS_METERS = 1000
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


def get_missing_origins(df: pd.DataFrame) -> set:
    '''Return the set of origin ids that have any null driving distance.

    Args:
        df: A DataFrame with columns ``id_orig`` and ``distance_m``.

    Returns:
        A set of ``id_orig`` values whose ``distance_m`` is null for at least
        one destination.
    '''
    missing_rows = df[pd.isnull(df[DISTANCE_DISTANCE_M])]
    return set(missing_rows[DISTANCE_ID_ORIG])


def matrix_response_to_long_df(source_names, dest_names, distances, durations) -> pd.DataFrame:
    '''Reshape ORS matrix grids into a long ``(id_orig, id_dest, distance_m, duration_s)`` frame.

    Args:
        source_names: Row labels (one per origin).
        dest_names: Column labels (one per destination).
        distances: ``distances[i][j]`` is the distance from ``source_names[i]``
            to ``dest_names[j]``, as returned by ORS.
        durations: ``durations[i][j]`` is the corresponding travel time, along
            the same route.

    Returns:
        A long-form DataFrame with columns ``id_orig``, ``id_dest``,
        ``distance_m``, ``duration_s``.
    '''
    rows = []
    for source, distance_row, duration_row in zip(source_names, distances, durations):
        for dest, distance_m, duration_s in zip(dest_names, distance_row, duration_row):
            rows.append({
                DISTANCE_ID_ORIG: source,
                DISTANCE_ID_DEST: dest,
                DISTANCE_DISTANCE_M: distance_m,
                DISTANCE_DURATION_S: duration_s,
            })
    return pd.DataFrame(
        rows,
        columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S],
    )


def _coerce_negative_metrics_to_null(df: pd.DataFrame) -> pd.DataFrame:
    '''Replace any negative ``distance_m`` or ``duration_s`` with NaN, in place.

    ORS signals "no route" with null, which becomes NaN and is recovered by the
    snap/retry path. A negative distance or duration is never a valid real-world
    value; if a routing backend ever emits one, treat it as no-route so it flows
    through the same recovery and never reaches the output CSV. ``0`` is kept.

    Args:
        df: Long-form DataFrame with ``distance_m`` and ``duration_s`` columns.

    Returns:
        The same DataFrame, with any negative ``distance_m``/``duration_s`` set to NaN.
    '''
    df.loc[df[DISTANCE_DISTANCE_M] < 0, DISTANCE_DISTANCE_M] = float('nan')
    df.loc[df[DISTANCE_DURATION_S] < 0, DISTANCE_DURATION_S] = float('nan')
    return df


def estimate_origin(origin: str, df: pd.DataFrame, locations: dict) -> pd.DataFrame:
    '''Estimate distances for an unroutable origin by snapping to a nearby neighbor.

    For each destination, look at all known sources within
    ``HAVERSINE_SNAP_RADIUS_METERS`` haversine of ``origin``. For each such
    source, compute ``distance_m + distance_to_mid`` (haversine offset from
    ``origin`` to that source). Take the minimum over those candidates.

    The chosen neighbor's ``duration_s`` is carried unchanged: the sub-1 km
    haversine offset is applied to ``distance_m`` only, because converting
    that offset to a travel time would require an invented speed constant.
    This is a small, bounded approximation affecting only unroutable (snapped)
    origins.

    Args:
        origin: The id of the origin to estimate distances for.
        df: A DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``
            of already-known driving distances.
        locations: Mapping from id to ``[longitude, latitude]``.

    Returns:
        A DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``,
        ``duration_s``, holding the best snapped estimate per destination.
        Empty if no in-range neighbor exists.
    '''
    candidates = df.rename(columns={DISTANCE_ID_ORIG: 'midpoint'}).copy()
    candidates[DISTANCE_ID_ORIG] = origin

    origin_latlon = tuple(reversed(locations[origin]))
    candidates['distance_to_mid'] = candidates['midpoint'].apply(
        lambda mid: haversine(origin_latlon, tuple(reversed(locations[mid])), unit=Unit.METERS)
    )

    in_range = candidates[candidates['distance_to_mid'] < HAVERSINE_SNAP_RADIUS_METERS].copy()
    if in_range.empty:
        return in_range[[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S]]

    in_range['estimated_m'] = in_range[DISTANCE_DISTANCE_M] + in_range['distance_to_mid']
    best = (in_range
            .sort_values('estimated_m')
            .groupby([DISTANCE_ID_ORIG, DISTANCE_ID_DEST])
            .first()
            .reset_index())
    best[DISTANCE_DISTANCE_M] = best['estimated_m']
    return best[[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S]]


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
        A long-form DataFrame with columns ``id_orig``, ``id_dest``,
        ``distance_m``, ``duration_s``.
    '''
    coords, source_indices, dest_indices = _build_locations_payload(
        locations, source_batch, dest_ids,
    )
    grids = query_matrix(coords, source_indices, dest_indices, matrix_url)
    return matrix_response_to_long_df(
        source_batch, dest_ids, grids['distance'], grids['duration'],
    )


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
                result = query_directions(locations[source], locations[dest], directions_url)
            except requests.exceptions.RequestException:
                _emit(f'directions raised for {source} -> {dest}: skipping',
                      _LEVEL_VV, log_fh, verbosity)
                continue
            if result is None:
                _emit(f'directions returned None for {source} -> {dest}: skipping',
                      _LEVEL_VV, log_fh, verbosity)
                continue
            distance, duration = result
            rows.append({
                DISTANCE_ID_ORIG: source,
                DISTANCE_ID_DEST: dest,
                DISTANCE_DISTANCE_M: distance,
                DISTANCE_DURATION_S: duration,
            })
    return pd.DataFrame(
        rows,
        columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S],
    )


def _snap_unroutable_origins(df: pd.DataFrame,
                             source_ids: list[str],
                             locations: dict[str, list[float]],
                             *,
                             log_fh: TextIO,
                             verbosity: int) -> pd.DataFrame:
    '''Replace null rows for unroutable origins with snapped haversine estimates.

    For each origin ORS could not route, calls ``estimate_origin`` to find an
    in-range haversine neighbor whose driving distance can be reused. Origins
    with no in-range neighbor are dropped (emit at ``_LEVEL_DEFAULT``); origins
    that snap successfully also emit at ``_LEVEL_DEFAULT``.

    Args:
        df: Long-form driving-distance DataFrame with column ``distance_m``.
        source_ids: All requested origin ids.
        locations: Mapping from id to ``[longitude, latitude]``.
        log_fh: Open writable text file handle. Snap events are written here.
        verbosity: Screen-output ceiling. Snap events emit at ``_LEVEL_DEFAULT``
            so they appear on screen regardless of this value.

    Returns:
        A new DataFrame with nulls dropped and snapped rows appended for any
        origin ORS could not route.
    '''
    if df.empty:
        null_origins = set()
        routed_origins = set()
    else:
        null_origins = get_missing_origins(df)
        routed_origins = set(df.loc[~pd.isnull(df[DISTANCE_DISTANCE_M]), DISTANCE_ID_ORIG])
    missing = null_origins | (set(source_ids) - routed_origins)
    if not missing:
        return df

    df = df.dropna(subset=[DISTANCE_DISTANCE_M])
    if df.empty:
        return pd.DataFrame(
            columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S],
        )

    snapped_parts = []
    for origin in missing:
        snapped = estimate_origin(origin, df, locations)
        if snapped.empty:
            _emit(f'unroutable origin {origin}: no neighbor within 1km, dropped',
                  _LEVEL_DEFAULT, log_fh, verbosity)
            continue
        _emit(f'unroutable origin {origin}: snapped to nearest haversine neighbor within 1km',
              _LEVEL_DEFAULT, log_fh, verbosity)
        snapped_parts.append(snapped)

    snapped_df = pd.concat(snapped_parts, ignore_index=True) if snapped_parts else pd.DataFrame(
        columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S],
    )
    return pd.concat([df, snapped_df], ignore_index=True)


def build_distance_matrix(*,
                          locations: dict[str, list[float]],
                          source_ids: list[str],
                          dest_ids: list[str],
                          matrix_url: str,
                          log_fh: TextIO,
                          verbosity: int = 0) -> pd.DataFrame:
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
        log_fh: Open writable text file handle for the run log. Per-batch progress,
            snap events, and retry detail are written here regardless of verbosity.
        verbosity: Screen-output ceiling (0 = quiet default, 1 = ``-v``, 2 = ``-vv``).

    Returns:
        A long-form DataFrame with columns ``id_orig``, ``id_dest``, ``distance_m``.
    '''
    source_ids = list(dict.fromkeys(source_ids))   # Dedup, preserve order.
    dest_ids = list(dict.fromkeys(dest_ids))

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
        columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S],
    )

    if failed_sources:
        retry_df = _retry_sources_individually(
            failed_sources, dest_ids, locations, matrix_url,
            log_fh=log_fh, verbosity=verbosity,
        )
        df = pd.concat([df, retry_df], ignore_index=True)

    # Treat any negative distance or duration as no-route before snapping, so it
    # flows through the same recovery as a real ORS null and never reaches the CSV.
    df = _coerce_negative_metrics_to_null(df)

    return _snap_unroutable_origins(
        df, source_ids, locations,
        log_fh=log_fh, verbosity=verbosity,
    )


def resume_from_partial_output(output_path, source_ids, dest_ids):
    '''Return ``(existing_df, remaining_pairs)`` for resuming a partial run.

    Fixes the upstream geolib bug where an existing partial output caused the
    CLI to return without writing anything. Instead, treat the existing file
    as a warm-start cache and compute the pairs still to fetch.

    Args:
        output_path: Path to a possibly-existing CSV with columns
            ``id_orig``, ``id_dest``, ``distance_m``, ``duration_s``.
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
        existing_df = pd.DataFrame(
            columns=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M, DISTANCE_DURATION_S],
        )

    present = set(zip(
        existing_df.get(DISTANCE_ID_ORIG, []),
        existing_df.get(DISTANCE_ID_DEST, []),
    ))
    all_pairs = [(s, d) for s in source_ids for d in dest_ids]
    remaining = [pair for pair in all_pairs if pair not in present]
    return existing_df, remaining
