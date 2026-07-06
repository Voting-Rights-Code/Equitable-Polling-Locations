"""Command line utility to pull RDH predicted VAP data for a given state and county."""

import argparse

from python.utils.pull_census_data import pull_RDH_predicted_vap_data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download block-level RDH predicted VAP projection data for a county.',
    )
    parser.add_argument(
        'state',
        help='U.S. state of interest. Two-letter abbreviation, e.g. GA or TX',
    )
    parser.add_argument(
        'county',
        help='County of interest. Full name with proper capitalization, e.g. Gwinnett County',
    )
    parser.add_argument(
        'census_year',
        help='Decennial census base year, e.g. 2020',
    )
    args = parser.parse_args()
    print(f'Downloading RDH predicted VAP data for {args.county}, {args.state} ({args.census_year})...')
    pull_RDH_predicted_vap_data(args.state, args.county, args.census_year)
    print('Done.')
