'''CLI: generate the driving-distance CSV for a given county config.

Reads census block centroids and the potential-locations CSV the solver
consumes, calls OpenRouteService to build a driving-distance matrix, and
writes the canonical three-column long-form CSV to
``datasets/driving/<location>/<location>_driving_distances.csv``.
'''
import argparse
import os
import sys
from datetime import datetime

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
from python.utils.ors_url import resolve_ors_url
from python.utils.utils import build_potential_locations_file_path, log_date_prefix


def build_arg_parser() -> argparse.ArgumentParser:
    '''Return the CLI argument parser.'''
    parser = argparse.ArgumentParser(
        description='Generate driving-distance CSV for a county config.',
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


def main(argv=None):
    '''CLI entry point.

    Args:
        argv: Optional list of argv-style strings; ``None`` uses ``sys.argv``.

    Returns:
        ``0`` on success. (Exits via ``sys.exit(main())`` from the if __name__ block.)
    '''
    args = build_arg_parser().parse_args(argv)
    config = PollingModelConfig.load_config(args.location_config)
    log_fh, log_path = _open_log_file(args.logdir, config.config_file_path)
    try:
        _tee(f'[{datetime.now().isoformat(timespec="seconds")}] starting for '
             f'{config.location} ({config.census_year})', log_fh)
        _tee(f'log: {log_path}', log_fh)

        locations, source_ids, dest_ids = derive_origins_and_destinations(config)
        _tee(f'origins: {len(source_ids)}, destinations: {len(dest_ids)}', log_fh)

        matrix_url = resolve_ors_url(args.server)
        _tee(f'ORS matrix URL: {matrix_url}', log_fh)

        if args.check_bad_locations:
            _tee('check-bad-locations mode: probing only, no output written', log_fh)
            df = build_distance_matrix(
                locations=locations, source_ids=source_ids, dest_ids=dest_ids,
                matrix_url=matrix_url,
                log_fh=log_fh, verbosity=args.verbose,
            )
            # Two failure modes: snap returned no row (origin absent from df) or some
            # dests still null after snapping (origin present with nulls). Union both.
            bad = get_missing_origins(df) | (set(source_ids) - set(df[DISTANCE_ID_ORIG]))
            _tee(f'unroutable origins: {sorted(bad)}', log_fh)
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
        return 0
    finally:
        log_fh.close()


if __name__ == '__main__':
    sys.exit(main())
