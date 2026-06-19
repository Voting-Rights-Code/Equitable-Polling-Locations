'''CLI: report per-county detour-ratio (driving / haversine) distribution.

Diagnostic for issue #226 Phase 1. Reads one or more combined driving-distance
CSVs and prints distribution statistics so border-truncation exposure can be
sized per county. Thin wrapper over python/utils/detour_ratio.py.
'''

import argparse
import sys

import pandas as pd

from python.solver.constants import DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M
from python.utils.detour_ratio import (
    load_distances_csv, compute_detour_ratios, summarize_detour_ratios,
)

_SUMMARY_COLUMNS = ['count', 'median', 'p90', 'p95', 'p99', 'max',
                    'count_over_1.5', 'count_over_2.0', 'count_over_3.0']


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog='analyze_detour_ratios_cli',
        description='Report per-county driving/haversine detour-ratio distribution (#226 diagnostic).',
    )
    parser.add_argument('paths', nargs='+',
                        help='Combined distances CSV file(s) from a driving run.')
    parser.add_argument('--out', default=None,
                        help='Optional path to write a per-pair ratio CSV.')
    return parser


def main(argv: list[str] | None = None) -> int:
    '''Entry point.

    Args:
        argv: Optional argument list (for testing). None uses sys.argv[1:].

    Returns:
        0 on success.
    '''
    args = _build_arg_parser().parse_args(argv)

    summary_rows = []
    per_pair_frames = []
    for path in args.paths:
        distances = load_distances_csv(path)
        ratios = compute_detour_ratios(distances)
        summary = summarize_detour_ratios(ratios)
        summary['file'] = path
        summary_rows.append(summary)

        if args.out is not None:
            per_pair_frames.append(pd.DataFrame({
                'file': path,
                'id_orig': distances[DISTANCE_ID_ORIG].values,
                'id_dest': distances[DISTANCE_ID_DEST].values,
                'distance_m': distances[DISTANCE_DISTANCE_M].values,
                'ratio': ratios.values,
            }))

    summary_df = pd.DataFrame(summary_rows).set_index('file')
    print(summary_df[_SUMMARY_COLUMNS].to_string())

    if args.out is not None:
        pd.concat(per_pair_frames, ignore_index=True).to_csv(args.out, index=False)
        print(f'Per-pair ratios written to {args.out}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
