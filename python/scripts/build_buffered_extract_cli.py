'''CLI: build a state-plus-50km buffered OSM extract (issue #226, in-container).

Internal plumbing the host orchestrator runs before booting ORS; it ensures
<state>-buffered.osm.pbf exists. Not meant for day-to-day use; thin wrapper over
python/utils/buffered_extract.py.
'''

import argparse
import sys

from python.utils.ors_setup import GEOFABRIK_STATE_SLUGS
from python.utils.buffered_extract import build_buffered_pbf


def main(argv: list[str] | None = None) -> int:
    '''Entry point.

    Args:
        argv: Optional argument list (for testing). None uses sys.argv[1:].

    Returns:
        0 on success.
    '''
    parser = argparse.ArgumentParser(
        prog='build_buffered_extract_cli',
        description='Build a <state>-buffered.osm.pbf from the full-US source (#226).',
    )
    parser.add_argument('state', help='Geofabrik state slug, e.g. georgia.')
    args = parser.parse_args(argv)

    if args.state not in GEOFABRIK_STATE_SLUGS:
        print(
            f'Unknown state slug: {args.state!r}. Use the full Geofabrik slug, '
            f'e.g. "georgia", "new-york", "district-of-columbia".'
        )
        sys.exit(2)

    buffered_path = build_buffered_pbf(args.state)
    print(buffered_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
