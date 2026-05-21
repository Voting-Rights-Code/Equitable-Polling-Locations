'''CLI: fetch the OpenStreetMap extract for a given US state from Geofabrik.

Writes the .pbf to ``.devcontainer/ors_data/<state>-latest.osm.pbf``. Run this
once per state before ``ors_up`` so the ORS container has data to build its
routing graph from.

Host-only: needs to write into the .devcontainer/ tree on the host filesystem.
Refuses to run inside the dev container.
'''
import argparse
import os
import sys
import urllib.request


GEOFABRIK_BASE_URL = 'https://download.geofabrik.de/north-america/us'

ORS_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '.devcontainer', 'ors_data',
)


STATE_TO_GEOFABRIK_SLUG = {
    'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas',
    'CA': 'california', 'CO': 'colorado', 'CT': 'connecticut', 'DE': 'delaware',
    'DC': 'district-of-columbia', 'FL': 'florida', 'GA': 'georgia',
    'HI': 'hawaii', 'ID': 'idaho', 'IL': 'illinois', 'IN': 'indiana',
    'IA': 'iowa', 'KS': 'kansas', 'KY': 'kentucky', 'LA': 'louisiana',
    'ME': 'maine', 'MD': 'maryland', 'MA': 'massachusetts', 'MI': 'michigan',
    'MN': 'minnesota', 'MS': 'mississippi', 'MO': 'missouri', 'MT': 'montana',
    'NE': 'nebraska', 'NV': 'nevada', 'NH': 'new-hampshire', 'NJ': 'new-jersey',
    'NM': 'new-mexico', 'NY': 'new-york', 'NC': 'north-carolina',
    'ND': 'north-dakota', 'OH': 'ohio', 'OK': 'oklahoma', 'OR': 'oregon',
    'PA': 'pennsylvania', 'RI': 'rhode-island', 'SC': 'south-carolina',
    'SD': 'south-dakota', 'TN': 'tennessee', 'TX': 'texas', 'UT': 'utah',
    'VT': 'vermont', 'VA': 'virginia', 'WA': 'washington', 'WV': 'west-virginia',
    'WI': 'wisconsin', 'WY': 'wyoming',
}


UNSUPPORTED_TERRITORIES = {'PR', 'GU', 'AS', 'MP', 'VI'}


def build_geofabrik_url(state_code: str) -> str:
    '''Return the Geofabrik download URL for a two-letter state code.

    Args:
        state_code: Two-letter US state code (uppercase).

    Returns:
        The Geofabrik HTTPS URL for that state's latest .osm.pbf.

    Raises:
        ValueError: If the code is a territory we explicitly don't support, or
            an unknown code.
    '''
    if state_code in UNSUPPORTED_TERRITORIES:
        raise ValueError(f'{state_code} not supported in v1 (territories have non-US Geofabrik paths)')
    slug = STATE_TO_GEOFABRIK_SLUG.get(state_code)
    if slug is None:
        raise ValueError(f'unknown state code: {state_code}')
    return f'{GEOFABRIK_BASE_URL}/{slug}-latest.osm.pbf'


def _ensure_host_only() -> None:
    '''Exit if running inside the dev container.

    Duplicated from ors_setup_cli.py rather than imported: this script is
    invoked from the host as a file path (not via the python.scripts.<name>
    module path), so cross-script imports inside the python/ package are
    not available.
    '''
    if os.path.exists('/.dockerenv'):
        print(
            'This command must be run from the host (you appear to be inside the '
            'dev container). Open a host terminal and try again.'
        )
        sys.exit(2)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Fetch the OSM extract for a US state from Geofabrik.',
    )
    parser.add_argument('--state', required=True, help='Two-letter US state code (e.g. GA).')
    parser.add_argument('--force', action='store_true',
                        help='Re-download even if the .pbf already exists.')
    return parser


def main(argv=None):
    '''CLI entry point.'''
    args = _build_arg_parser().parse_args(argv)
    _ensure_host_only()

    state_code = args.state.upper()
    url = build_geofabrik_url(state_code)
    os.makedirs(ORS_DATA_DIR, exist_ok=True)
    target = os.path.join(ORS_DATA_DIR, os.path.basename(url))

    if os.path.exists(target) and not args.force:
        print(f'{target} already exists; pass --force to re-download.')
        return 0

    print(f'Downloading {url} -> {target}')
    urllib.request.urlretrieve(url, target)
    if os.path.exists(target):
        print(f'Done: {os.path.getsize(target):,} bytes')
    else:
        print('Done.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
