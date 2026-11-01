"""Command line utility to pull census data for a given state and county."""

import argparse

from python.utils.pull_census_data import pull_census_data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Pull census redistricting data (P3/P4 tables and TIGER shapefiles) for a given county.',
    )
    parser.add_argument(
        'state',
        help='U.S. state of interest. Two letter abbreviation, e.g. MD or NY',
    )
    parser.add_argument(
        'county',
        help='County of interest. Full name, with proper capitalization, e.g. Norfolk city or Gwinnett County',
    )
    parser.add_argument(
        'census_year',
        help='Decennial census year of interest, e.g. 2020',
    )
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='Print per-table and per-file progress while downloading.',
    )
    args = parser.parse_args()
    print(f'Downloading census data for {args.county}, {args.state} ({args.census_year})...')
    pull_census_data(args.state, args.county, args.census_year, verbose=args.verbose > 0)
    print('Completed.')
