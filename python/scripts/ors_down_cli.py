'''CLI: stop the sibling ORS container.

The routing graph for each state lives under ``datasets/ors_graphs/<state>-buffered/``
on the host filesystem (bind-mounted into the container). It survives
``ors_down_cli`` automatically; to force a fresh rebuild for a given state,
delete that state's directory manually:

    rm -rf datasets/ors_graphs/<state>-buffered

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

    Inlined rather than imported: this script is invoked from the host as a
    file path (not via the python.scripts.<name> module path), so cross-script
    imports inside the python/ package are not available.
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
    return parser


def main(argv=None):
    '''CLI entry point.

    Args:
        argv: Optional list of argv-style strings; ``None`` uses ``sys.argv``.

    Returns:
        ``0`` on success.
    '''
    _build_arg_parser().parse_args(argv)
    _ensure_host_only()

    # ``docker compose down`` here also requires ORS_STATE to be set because
    # the compose file references it. The actual value doesn't matter for
    # teardown — compose just needs to be able to parse the file — so we set
    # a harmless placeholder.
    env = os.environ.copy()
    env.setdefault('ORS_STATE', 'unset')
    subprocess.run(
        ['docker', 'compose', '-f', COMPOSE_FILE, 'down'],
        env=env,
        check=True,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
