'''CLI: stop the sibling ORS container. Preserves built graphs by default.

Pass --purge-graphs to also remove the ors_graphs named volume (use after
swapping in a new state's .pbf to force a clean rebuild on next ors_up).

Host-only.
'''
import argparse
import os
import subprocess
import sys


COMPOSE_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', '.devcontainer', 'docker-compose.ors.yml',
    )
)


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
    _ensure_host_only()

    cmd = ['docker', 'compose', '-f', COMPOSE_FILE, 'down']
    if args.purge_graphs:
        cmd.append('-v')
    subprocess.run(cmd, check=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
