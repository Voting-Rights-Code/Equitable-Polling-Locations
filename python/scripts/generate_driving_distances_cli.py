'''CLI: generate the driving-distance CSV for a given county config.

Reads census block centroids and the potential-locations CSV from disk
(no DB read or census pulls enabled), calls OpenRouteService to build a 
driving-distance matrix, and writes the canonical three-column long-form 
CSV to ``datasets/driving/<location>/<location>_driving_distances.csv``.
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
    POT_LOC_LAT_LON,
    POT_LOC_LOCATION,
    TIGER20_GEOID20,
    TIGER20_INTPTLAT20,
    TIGER20_INTPTLON20,
)
from python.solver.model_config import PollingModelConfig
from python.solver.model_data import get_blocks_gdf, load_potential_locations_csv
from python.utils.directory_constants import DRIVING_DIR
from python.utils.driving_distance_matrix import (
    build_distance_matrix,
    get_origins_with_blank_distances,
    identify_unmatched_pairs,
)
from python.utils.ors_setup import GEOFABRIK_STATE_SLUGS, state_slug_from_location
from python.utils.ors_url import resolve_ors_url
from python.utils.utils import build_potential_locations_file_path, log_date_prefix


def build_arg_parser() -> argparse.ArgumentParser:
    '''Return the CLI argument parser. Split out into its own function
    so it can have its own unit test, complying with updated testing standards.'''

    parser = argparse.ArgumentParser(
        description='Generate driving-distance CSV for a county config. Requires the '
        'relevant config files and potential_locations data to be stored locally (not on the DB) '
        'and that the relevant TIGER files are already on disk.',
    )
    # testing fixtures are a sample of Gwinnett County, 2020 data
    # these have no state (_<ST>) suffix
    # this flag accommodates this anomaly.
    parser.add_argument(
        '--state', default=None,
        help='Geofabrik state slug override (e.g. "georgia", "new-york"). '
             'When omitted, derived by parsing the trailing _<ST> postal code '
             'from the config location.',
    )
    #path to config argument
    parser.add_argument(
        '-l', '--location-config', required=True,
        help=(
            'Path to a PollingModelConfig YAML, e.g. '
            'datasets/configs/testing/testing_config_driving.yaml. Mirrors the '
            'path form accepted by model_run_cli.'
        ),
    )
    #set ORS urls
    parser.add_argument(
        '--server', default=None,
        help='ORS matrix endpoint URL (overrides $ORS_URL).',
    )
    #logging
    parser.add_argument(
        '--logdir', default='./logs', help='Directory to write the run log into.',
    )
    #verbosity
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
    '''Build (locations_dict, source_ids, dest_ids) from the config. This 
    is the data format expected by ORS to build distance matrix.

    Args:
        config: A loaded ``PollingModelConfig``.

    Returns:
        A tuple ``(locations, source_ids, dest_ids)``:
            - ``locations``: ``id -> [longitude, latitude]`` dict.
            - ``source_ids``: census block GEOIDs (origins).
            - ``destination_ids``: potential-location ``Location`` values (destinations).
    '''

    # load local block geography and potential locations data.
    blocks_gdf = get_blocks_gdf(config.census_year, config.location)
    potential_locations_df = load_potential_locations_csv(
        build_potential_locations_file_path(config.location),
    )

    # get source id and location data from TIGER
    source_ids = blocks_gdf[TIGER20_GEOID20].astype(str).tolist()
    coords = blocks_gdf[[TIGER20_INTPTLON20, TIGER20_INTPTLAT20]].astype(float).values.tolist()
    locations = dict(zip(source_ids, coords))

    # get destination id and location coordinates from potential_location data
    destination_ids = potential_locations_df[POT_LOC_LOCATION].tolist()
    joint_coords = potential_locations_df[POT_LOC_LAT_LON].str.split(',', expand=True).astype(float)
    dest_coords = joint_coords[[1, 0]].values.tolist()  # column 0 is lat, column 1 is lon — reorder to [lon, lat]
    locations.update(dict(zip(destination_ids, dest_coords)))

    return locations, source_ids, destination_ids


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
    '''Write ``message`` to screen (optionally) and to ``log_fh``, flushing.'''
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
    '''Formatting function for _report_unrouted_origin's logging below.
    Return one indented ``id (lat=..., lon=...)`` line per origin, sorted by id.

    Args:
        origins: Origin ids to list.
        locations: Mapping from id to ``[longitude, latitude]``.

    Returns:
        A list of formatted message lines.
    '''
    lines = []
    for origin in sorted(origins):
        longitude, latitude = locations.get(origin, [None, None])
        lines.append(f'  {origin} (lat={latitude}, lon={longitude})')
    return lines


def _report_unrouted_origins(df: pd.DataFrame,
                             source_ids: list[str],
                             locations: dict[str, list[float]],
                             log_fh: TextIO,
                             *,
                             output_path: str) -> set[str]:
    '''Detects origins that have not been properly filled by previous runs and provides
    instructions on next steps. TODO: flagging only happens at origin level, not pair level. 
    See docs/to_run.md (section "Unroutable origins fail the run") for details. see #338

    Two failure shapes are distinguished: absent origins with no rows at all recorded in the df
    on file and blank origins whose rows carry a blank ``distance_m``. 
    
    Blank origins are caused by human editing of unroutable origins that need
    to be entered manually or have the row deleted TODO: see #338.
    
    The absent origins are either due to an aborted run on generate_driving_distances_cli
    or the existence of unroutable origins that cannot be automatically routed. These need 
    human review.

    Args:
        df: Long-form distance DataFrame to check 
        source_ids: All requested origin ids.
        locations: Mapping from id to ``[longitude, latitude]``, used to print
            each missing origin's coordinates.
        log_fh: Open writable log file handle.
        output_path: Path of the output CSV that was just written, named in
            the failure message.
        
    Returns:
        The set of origin ids lacking a usable distance; empty when every
        origin has one.
    '''
    #define the two missing modes this function deals with:
    blank_origins = get_origins_with_blank_distances(df)
    absent_origins = set(source_ids) - set(df[DISTANCE_ID_ORIG])

    unrouted = blank_origins | absent_origins
    if not unrouted:
        return unrouted # nothing unrouted — every origin has a usable distance

    #otherwise log missing data
    lines = []
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
        output CSV has a blank ``distance_m``. Exits via ``sys.exit(main())``
        from the if __name__ block.
    '''
    args = build_arg_parser().parse_args(argv)

    # Validate an explicit --state for testing fixtures
    if args.state is not None:
        _reject_unknown_slug(args.state)

    #check url
    matrix_url = resolve_ors_url(args.server)
    _assert_ors_reachable(matrix_url)

    #load config
    config = PollingModelConfig.load_config(args.location_config)

    #check state validity before ORS run
    state = args.state
    if state is None:
        try:
            state = state_slug_from_location(config.location)
        except ValueError as exc:
            # Expected exception for the 'testing' fixture
            print(
                f'Couldn\'t derive state from config (location={config.location!r}; {exc}).\n'
                f'Either rename the location to end in _<ST> '
                f'(e.g. {config.location}_GA) or pass an explicit override:\n'
                f'  python3 run.py generate_driving_distances_cli --state georgia '
                f'-l {args.location_config}'
            )
            sys.exit(2)
    _reject_unknown_slug(state)

    #begin logging.
    log_fh, log_path = _open_log_file(args.logdir, config.config_file_path)
    try:
        _tee(f'[{datetime.now().isoformat(timespec="seconds")}] starting for '
             f'{config.location} ({config.census_year})', log_fh)
        _tee(f'log: {log_path}', log_fh)

        locations, source_ids, dest_ids = derive_origins_and_destinations(config)
        _tee(f'origins: {len(source_ids)}, destinations: {len(dest_ids)}', log_fh)

        _tee(f'ORS matrix URL: {matrix_url}', log_fh)

        ###create and write distance matrix###

        #identify missing data if any
        output_path = build_output_csv_path(config.location)
        existing_df, remaining_pairs = identify_unmatched_pairs(
            output_path, source_ids, dest_ids,
        )
        _tee(
            f'resume: {len(existing_df)} rows present, '
            f'{len(remaining_pairs)} pairs to fetch', 
            log_fh,
        )
        #if all origins destination pairs are in the dataset
        if not remaining_pairs:
            write_output_csv(existing_df, output_path)
            _tee(
                f'no new pairs to fetch; rewrote {len(existing_df)} rows to {output_path}',
                log_fh,
            )
            #verify that they have distances entered.
            if _report_unrouted_origins(existing_df, source_ids, locations, log_fh,
                                        output_path=output_path):
                return 1
            return 0

        #otherwise, some pairs are missing.
        #try to fetch these pairs
        remaining_sources = sorted({pair[0] for pair in remaining_pairs})
        remaining_dests = sorted({pair[1] for pair in remaining_pairs})
        new_df = build_distance_matrix(
            locations=locations,
            source_ids=remaining_sources,
            dest_ids=remaining_dests,
            matrix_url=matrix_url,
            log_fh=log_fh, verbosity=args.verbose,
        )

        #concatenate results and drop duplicates
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(
            subset=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST], keep='last',
        )

        #write outputs and report missing data
        write_output_csv(combined, output_path)
        _tee(f'wrote {len(combined)} rows to {output_path}', log_fh)
        if _report_unrouted_origins(combined, source_ids, locations, log_fh,
                                    output_path=output_path):
            return 1
        return 0
    finally:
        log_fh.close()


if __name__ == '__main__':
    sys.exit(main())
