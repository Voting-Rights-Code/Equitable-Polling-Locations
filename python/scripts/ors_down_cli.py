'''CLI: stop the sibling ORS container. Preserves built graphs by default.

Pass --purge-graphs to also remove the ors_graphs named volume (use after
swapping in a new state's .pbf to force a clean rebuild on next ors_up).

Host-only.
'''
import argparse
import subprocess
import sys

from python.scripts.ors_setup_cli import ensure_host_only
from python.scripts.ors_up_cli import COMPOSE_FILE


def _build_arg_parser() -> argparse.ArgumentParser:
    '''Return the CLI argument parser.

    Returns:
        Configured ``ArgumentParser`` for ``ors_down_cli``.
    '''
    parser = argparse.ArgumentParser(
        description='Stop the sibling ORS container.',
    )
    parser.add_argument(
        '--purge-graphs', action='store_true',
        help='Also remove the ors_graphs named volume (forces clean rebuild next time).',
    )
    return parser


def main(argv=None):
    '''CLI entry point.

    Args:
        argv: Optional list of argv-style strings; ``None`` uses ``sys.argv``.

    Returns:
        ``0`` on success.
    '''
    args = _build_arg_parser().parse_args(argv)
    ensure_host_only()

    cmd = ['docker', 'compose', '-f', COMPOSE_FILE, 'down']
    if args.purge_graphs:
        cmd.append('-v')
    subprocess.run(cmd, check=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
