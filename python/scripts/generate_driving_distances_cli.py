'''CLI: generate the driving-distance CSV for a given county config.

Reads census block centroids and the potential-locations CSV the solver
consumes, calls OpenRouteService to build a driving-distance matrix, and
writes the canonical three-column long-form CSV to
``datasets/driving/<location>/<location>_driving_distances.csv``.
'''
import argparse
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import TextIO

import pandas as pd

from python.solver.constants import (
    DISTANCE_DISTANCE_M,
    DISTANCE_ID_DEST,
    DISTANCE_ID_ORIG,
    TIGER20_GEOID20,
    TIGER20_INTPTLAT20,
    TIGER20_INTPTLON20,
)
from python.solver.model_config import PollingModelConfig
from python.solver.model_data import get_blocks_gdf, load_potential_locations_csv
from python.utils.directory_constants import DRIVING_DIR
from python.utils.driving_distance_matrix import (
    build_distance_matrix,
    get_missing_origins,
    resume_from_partial_output,
)
from python.utils.ors_setup import GEOFABRIK_STATE_SLUGS, state_slug_from_location
from python.utils.ors_url import resolve_ors_url
from python.utils.utils import build_potential_locations_file_path, log_date_prefix


def build_arg_parser() -> argparse.ArgumentParser:
    '''Return the CLI argument parser.'''
    # A separate function (unlike older sibling CLIs that parse inline) so
    # tests can exercise parsing directly, per this repo's TDD mandate.
    parser = argparse.ArgumentParser(
        description='Generate driving-distance CSV for a county config.',
    )
    parser.add_argument(
        '--state', default=None,
        # The override exists because not every config location can derive a
        # state: the 'testing' fixture's location has no _<ST> suffix. It also
        # lets an operator deliberately point at a different state's graph.
        help='Geofabrik state slug override (e.g. "georgia", "new-york"). '
             'When omitted, derived by parsing the trailing _<ST> postal code '
             'from the config location.',
    )
    parser.add_argument(
        '-l', '--location-config', required=True,
        help=(
            'Path to a PollingModelConfig YAML, e.g. '
            'datasets/configs/testing/testing_config_driving.yaml. Mirrors the '
            'path form accepted by model_run_cli.'
        ),
    )
    parser.add_argument(
        '--server', default=None,
        help='ORS matrix endpoint URL (overrides $ORS_URL).',
    )
    parser.add_argument(
        '--logdir', default='./logs', help='Directory to write the run log into.',
    )
    parser.add_argument(
        '--check-bad-locations', action='store_true',
        help='Probe-only mode: list unroutable origins and exit without writing output.',
    )
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='Increase screen verbosity (-v or -vv). The log file captures everything regardless.',
    )
    return parser


def build_output_csv_path(location: str) -> str:
    '''Return the canonical output CSV path for a location.'''
    out_dir = os.path.join(DRIVING_DIR, location)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f'{location}_driving_distances.csv')


def derive_origins_and_destinations(config):
    '''Build (locations_dict, source_ids, dest_ids) from the config.

    Args:
        config: A loaded ``PollingModelConfig``.

    Returns:
        A tuple ``(locations, source_ids, dest_ids)``:
            - ``locations``: ``id -> [longitude, latitude]`` dict.
            - ``source_ids``: census block GEOIDs (origins).
            - ``dest_ids``: potential-location ``Location`` values (destinations).
    '''
    # Always reads local files, disregarding config.data_source — structural,
    # not a choice: data_source is not a YAML field at all. load_config REJECTS
    # a YAML that contains it (ValueError 'unknown fields' — IGNORE_ON_LOAD in
    # python/solver/model_config.py excludes it from allowed_fields), so here
    # the field always holds its DATA_SOURCE_CSV default. Only model_run_db_cli
    # sets 'db', at runtime, as a came-from-the-DB provenance marker — and this
    # CLI loads configs from YAML only. DB-backed generation would be a new
    # feature (e.g. a generate_driving_distances_db_cli sibling, mirroring the
    # model_run_cli / model_run_db_cli split).
    blocks_gdf = get_blocks_gdf(config.census_year, config.location)
    pots_df = load_potential_locations_csv(
        build_potential_locations_file_path(config.location),
    )

    locations = {}
    source_ids = []
    for _, row in blocks_gdf.iterrows():
        geoid = str(row[TIGER20_GEOID20])
        locations[geoid] = [float(row[TIGER20_INTPTLON20]), float(row[TIGER20_INTPTLAT20])]
        source_ids.append(geoid)

    extract_lon_lat = _pick_coord_extractor(list(pots_df.columns))
    dest_ids = []
    for _, row in pots_df.iterrows():
        loc_id = str(row['Location'])
        lon, lat = extract_lon_lat(row)
        locations[loc_id] = [lon, lat]
        dest_ids.append(loc_id)

    return locations, source_ids, dest_ids


def _pick_coord_extractor(columns):
    '''Return a callable that reads ``(lon, lat)`` from a potential-locations row.

    The project carries two CSV schemas in the wild:

    - Separate ``Latitude`` / ``Longitude`` columns (e.g. the ``testing`` fixture).
    - A single combined column named ``"Lat, Long"`` or ``"Lat, Lon"`` whose
      value is a string like ``"32.707497 , -97.252456"`` (lat first, comma,
      lon; tolerating whitespace) — used by Tarrant_County_TX.

    Args:
        columns: Sequence of column names from the loaded DataFrame.

    Returns:
        A callable ``extract(row) -> (lon, lat)`` for use in the dest loop.

    Raises:
        ValueError: If neither schema is present in the columns.
    '''
    if 'Longitude' in columns and 'Latitude' in columns:
        def extract_separate(row):
            return float(row['Longitude']), float(row['Latitude'])
        return extract_separate

    combined_col = next(
        (col for col in columns if col.lower().replace(' ', '').startswith('lat,l')),
        None,
    )
    if combined_col is not None:
        def extract_combined(row):
            value = str(row[combined_col])
            parts = value.split(',')
            if len(parts) != 2:
                raise ValueError(
                    f'Expected lat, lon format in combined column {combined_col!r}, got: {value!r}'
                )
            return float(parts[1].strip()), float(parts[0].strip())
        return extract_combined

    raise ValueError(
        f'Potential-locations CSV has neither separate Latitude/Longitude '
        f'columns nor a combined Lat, Lon column. Got columns: {list(columns)}'
    )


def write_output_csv(df, path: str) -> None:
    '''Write the canonical 3-column CSV (id_orig, id_dest, distance_m).'''
    df[[DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M]].to_csv(path, index=False)


def _open_log_file(logdir: str, config_file_path: str):
    '''Return an open log file handle for this run, plus its path.'''
    os.makedirs(logdir, exist_ok=True)
    basename = os.path.basename(config_file_path)
    log_path = os.path.join(logdir, f'{log_date_prefix()}_{basename}_driving_distances.log')
    # Caller closes the handle in a try/finally; deliberately not a context manager.
    log_fh = open(log_path, 'a', encoding='utf-8')  # pylint: disable=consider-using-with
    return log_fh, log_path


def _tee(message: str, log_fh, *, to_screen: bool = True) -> None:
    '''Write ``message`` to stdout (optionally) and to ``log_fh``, flushing.'''
    if to_screen:
        print(message)
    log_fh.write(message + '\n')
    log_fh.flush()


def _assert_ors_reachable(matrix_url: str) -> None:
    '''Probe the ORS health endpoint; exit with a clear message if unreachable.

    Args:
        matrix_url: ORS matrix URL; the health URL is derived by stripping
            ``/matrix/...`` and appending ``/health``.
    '''
    health_url = matrix_url.rsplit('/matrix/', 1)[0] + '/health'
    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:
            if response.getcode() == 200:
                return
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        pass
    print(
        f'ORS is not reachable at {health_url}. From the host, run\n'
        f'  python3 run.py generate_driving_distances_cli -l <config>\n'
        f'which auto-orchestrates the ORS lifecycle. To start ORS manually:\n'
        f'  python3 run.py ors_up_cli <state>'
    )
    sys.exit(1)


def _origin_lines(origins: set[str], locations: dict[str, list[float]]) -> list[str]:
    '''Return one indented ``id (lat=..., lon=...)`` line per origin, sorted by id.

    Args:
        origins: Origin ids to list.
        locations: Mapping from id to ``[longitude, latitude]``.

    Returns:
        A list of formatted message lines.
    '''
    lines = []
    for origin in sorted(origins):
        longitude, latitude = locations.get(origin, (None, None))
        lines.append(f'  {origin} (lat={latitude}, lon={longitude})')
    return lines


def _report_unrouted_origins(df: pd.DataFrame,
                             source_ids: list[str],
                             locations: dict[str, list[float]],
                             log_fh: TextIO,
                             *,
                             output_path: str | None = None) -> set[str]:
    '''Detect origins lacking a usable distance and print a mode-accurate summary.

    Two failure shapes are distinguished: origins with no rows at all in
    ``df`` (ORS could not route them), and origins whose rows carry a blank
    ``distance_m`` — possible only via a hand-edited output CSV, and NOT
    recovered by a plain rerun, because resume counts those pairs as present.

    Args:
        df: Long-form distance DataFrame to check — the build result in probe
            mode, or the just-written frame in the write paths.
        source_ids: All requested origin ids.
        locations: Mapping from id to ``[longitude, latitude]``, used to print
            each missing origin's coordinates.
        log_fh: Open writable log file handle.
        output_path: Path of the output CSV that was just written, named in
            the failure message. ``None`` in probe mode, where no CSV exists
            and the message must not reference one (or resume).

    Returns:
        The set of origin ids lacking a usable distance; empty when every
        origin has one.
    '''
    blank_origins = get_missing_origins(df)
    absent_origins = set(source_ids) - set(df[DISTANCE_ID_ORIG])
    unrouted = blank_origins | absent_origins
    if not unrouted:
        return unrouted

    lines = []
    if output_path is None:
        lines.append(f'{len(unrouted)} origin(s) could not be routed; correct the '
                     'underlying data (e.g. a bad centroid) and re-run the probe:')
        lines.extend(_origin_lines(unrouted, locations))
    else:
        if absent_origins:
            lines.append(f'{len(absent_origins)} origin(s) could not be routed and have '
                         f'no rows in {output_path}; correct the underlying data (e.g. a '
                         'bad centroid) and rerun — resume will fetch only the missing '
                         'pairs:')
            lines.extend(_origin_lines(absent_origins, locations))
        if blank_origins:
            lines.append(f'{len(blank_origins)} origin(s) in the existing CSV '
                         f'({output_path}) have a blank distance_m; fill in the value, or '
                         'delete the row so resume re-fetches it — rerunning without a '
                         'change will NOT fetch these pairs:')
            lines.extend(_origin_lines(blank_origins, locations))
    _tee('\n'.join(lines), log_fh)
    return unrouted


def _reject_unknown_slug(state: str) -> None:
    '''Exit with code 2 if state is not a known Geofabrik state slug.

    Args:
        state: The candidate Geofabrik state slug to validate.
    '''
    if state not in GEOFABRIK_STATE_SLUGS:
        print(
            f'Unknown state slug: {state!r}. Use the full Geofabrik slug, '
            f'e.g. "georgia", "new-york", "district-of-columbia". See '
            f'python/utils/ors_setup.py for the full list.'
        )
        sys.exit(2)


def main(argv=None):
    '''CLI entry point.

    Args:
        argv: Optional list of argv-style strings; ``None`` uses ``sys.argv``.

    Returns:
        ``0`` on success; ``1`` when any requested origin lacks a usable
        distance — either ORS could not route it, or its row in the existing
        output CSV has a blank ``distance_m`` (in the normal mode the CSV of
        completed work is still written first). Exits via ``sys.exit(main())``
        from the if __name__ block.
    '''
    args = build_arg_parser().parse_args(argv)

    # Validate an explicit --state before any ORS or config work, so a typo
    # fails fast without requiring a running ORS or a readable config file.
    if args.state is not None:
        _reject_unknown_slug(args.state)

    matrix_url = resolve_ors_url(args.server)
    _assert_ors_reachable(matrix_url)

    config = PollingModelConfig.load_config(args.location_config)

    state = args.state
    if state is None:
        try:
            state = state_slug_from_location(config.location)
        except ValueError as exc:
            # Expected for synthetic configs whose location field doesn't follow
            # the <Name>_<ST> convention — e.g. the 'testing' fixture — which is
            # the case that motivated the --state override in the first place.
            print(
                f'Couldn\'t derive state from config (location={config.location!r}; {exc}).\n'
                f'Either rename the location to end in _<ST> '
                f'(e.g. {config.location}_GA) or pass an explicit override:\n'
                f'  python3 run.py generate_driving_distances_cli --state georgia '
                f'-l {args.location_config}'
            )
            sys.exit(2)
    _reject_unknown_slug(state)
    log_fh, log_path = _open_log_file(args.logdir, config.config_file_path)
    try:
        _tee(f'[{datetime.now().isoformat(timespec="seconds")}] starting for '
             f'{config.location} ({config.census_year})', log_fh)
        _tee(f'log: {log_path}', log_fh)

        locations, source_ids, dest_ids = derive_origins_and_destinations(config)
        _tee(f'origins: {len(source_ids)}, destinations: {len(dest_ids)}', log_fh)

        _tee(f'ORS matrix URL: {matrix_url}', log_fh)

        if args.check_bad_locations:
            _tee('check-bad-locations mode: probing only, no output written', log_fh)
            df = build_distance_matrix(
                locations=locations, source_ids=source_ids, dest_ids=dest_ids,
                matrix_url=matrix_url,
                log_fh=log_fh, verbosity=args.verbose,
            )
            # TODO(#325): detection here is origin-level — an origin that routes
            # to some destinations but not others (pair-level incompleteness) is
            # not flagged here; it is caught downstream at model-run time by
            # model_data's completeness check. Known gap, deliberately not fixed
            # in this ticket.
            if _report_unrouted_origins(df, source_ids, locations, log_fh):
                return 1
            _tee('no unroutable origins found', log_fh)
            return 0

        output_path = build_output_csv_path(config.location)
        existing_df, remaining_pairs = resume_from_partial_output(
            output_path, source_ids, dest_ids,
        )
        _tee(
            f'resume: {len(existing_df)} rows present, '
            f'{len(remaining_pairs)} pairs to fetch',
            log_fh,
        )

        if not remaining_pairs:
            write_output_csv(existing_df, output_path)
            _tee(
                f'no new pairs to fetch; rewrote {len(existing_df)} rows to {output_path}',
                log_fh,
            )
            # A hand-edited CSV can satisfy every pair yet leave distance_m
            # blank — still a failure the solver would hit later.
            if _report_unrouted_origins(existing_df, source_ids, locations, log_fh,
                                        output_path=output_path):
                return 1
            return 0

        remaining_sources = sorted({pair[0] for pair in remaining_pairs})
        remaining_dests = sorted({pair[1] for pair in remaining_pairs})
        new_df = build_distance_matrix(
            locations=locations,
            source_ids=remaining_sources,
            dest_ids=remaining_dests,
            matrix_url=matrix_url,
            log_fh=log_fh, verbosity=args.verbose,
        )

        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(
            subset=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST], keep='last',
        )

        write_output_csv(combined, output_path)
        _tee(f'wrote {len(combined)} rows to {output_path}', log_fh)
        # The CSV is written first so completed work is never lost: on a
        # failure here, a human fixes the flagged origins and reruns, and
        # resume fetches only the missing pairs.
        if _report_unrouted_origins(combined, source_ids, locations, log_fh,
                                    output_path=output_path):
            return 1
        return 0
    finally:
        log_fh.close()


if __name__ == '__main__':
    sys.exit(main())
