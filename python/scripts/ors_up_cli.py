'''CLI: bring up the sibling ORS container for a given state.

Workflow for ``python3 run.py ors_up_cli <state>``:

1. Validate the state slug against ``GEOFABRIK_STATE_SLUGS``.
2. Download ``<state>-latest.osm.pbf`` to ``datasets/openrouteservice/`` if
   missing (logs a clear message; downloads are hundreds of MB).
3. Ensure the per-state graph cache dir ``datasets/ors_graphs/<state>/``
   exists so the bind mount resolves to a host-owned (not root-owned) dir.
4. Spawn the ORS container via ``docker compose up -d`` with ``ORS_STATE``
   set in the subprocess env so compose substitutes it into both the
   ``ors.engine.source_file`` path and the per-state graph bind mount.
5. Poll ``/ors/v2/health`` until 200 or the 45-minute timeout expires
   (state-sized graphs can take 20-30 min on first boot).

Host-only.
'''
import argparse
import os
import subprocess
import sys
import time
import typing
import urllib.error
import urllib.request
from datetime import datetime

# This script is invoked from the host as a file path (not via
# python -m python.scripts.<name>), so cross-script imports must reach the
# stdlib-only utils. Importing python.utils.ors_setup triggers
# python/__init__.py which imports numpy — that's available on the host
# only if the user has the project conda env active. Fall back to a
# file-path import so host-side use without project deps still works.
try:
    from python.utils.ors_setup import GEOFABRIK_STATE_SLUGS, download_pbf_if_missing
except ImportError:  # pragma: no cover - host-only fallback path
    import importlib.util  # pylint: disable=import-outside-toplevel  # fallback for host invocation without project conda env
    _here = os.path.dirname(os.path.abspath(__file__))
    _setup_path = os.path.normpath(os.path.join(_here, '..', 'utils', 'ors_setup.py'))
    _setup_spec = importlib.util.spec_from_file_location('ors_setup', _setup_path)
    if _setup_spec is None or _setup_spec.loader is None:
        raise ImportError(  # pylint: disable=raise-missing-from  # already inside except ImportError; chaining adds noise
            f'could not load python/utils/ors_setup.py from {_setup_path}'
        )
    _setup_module = importlib.util.module_from_spec(_setup_spec)
    _setup_spec.loader.exec_module(_setup_module)
    GEOFABRIK_STATE_SLUGS = _setup_module.GEOFABRIK_STATE_SLUGS
    download_pbf_if_missing = _setup_module.download_pbf_if_missing


def _ensure_host_only() -> None:
    '''Exit if running inside the dev container.

    Inlined rather than imported: this script is invoked from the host as a
    file path (not via ``python -m python.scripts.<name>``), so cross-script
    imports inside the python/ package are not always available.
    '''
    if os.path.exists('/.dockerenv'):
        print(
            'This command must be run from the host (you appear to be inside the '
            'dev container). Open a host terminal and try again.'
        )
        sys.exit(2)


HEALTH_POLL_INTERVAL_S = 10
HEALTH_POLL_TIMEOUT_S = 2700  # 45 minutes (state-sized graphs can take 20-30 min).
DEFAULT_HEALTH_URL = 'http://localhost:8080/ors/v2/health'
COMPOSE_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', '.devcontainer', 'docker-compose.ors.yml',
    )
)
ORS_GRAPHS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', 'datasets', 'ors_graphs',
    )
)


def poll_health(url: str, *, timeout_s: int = HEALTH_POLL_TIMEOUT_S,
                poll_interval_s: int = HEALTH_POLL_INTERVAL_S) -> bool:
    '''Poll ``url`` until it returns 200 or ``timeout_s`` elapses.

    Args:
        url: ORS health endpoint URL.
        timeout_s: Maximum seconds to wait before giving up.
        poll_interval_s: Seconds between polls.

    Returns:
        True if a 200 was observed; False on timeout (or persistent error).
    '''
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.getcode() == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(poll_interval_s)
    return False


def _tee(message: str, log_fh: typing.IO[str]) -> None:
    '''Print ``message`` to stdout and append it to ``log_fh`` with a flush.

    Args:
        message: Text to emit.
        log_fh: Open writable file handle for the run log.
    '''
    print(message)
    log_fh.write(message + '\n')
    log_fh.flush()


def _build_arg_parser() -> argparse.ArgumentParser:
    '''Build the CLI argument parser.

    Returns:
        Configured ``argparse.ArgumentParser`` for this script.
    '''
    parser = argparse.ArgumentParser(
        description='Start the sibling ORS container for a given state and wait for it to be ready.',
    )
    parser.add_argument(
        'state',
        help='Geofabrik state slug, e.g. "georgia", "new-york", "district-of-columbia".',
    )
    parser.add_argument(
        '--health-url', default=DEFAULT_HEALTH_URL,
        help=f'Health endpoint to poll (default {DEFAULT_HEALTH_URL}).',
    )
    parser.add_argument(
        '--logdir', default='./logs', help='Directory to write the run log into.',
    )
    return parser


def main(argv=None):
    '''CLI entry point.

    Args:
        argv: Optional argv list (mainly for testing). ``None`` means use
            ``sys.argv[1:]``.

    Returns:
        ``0`` on success. Calls ``sys.exit(1)`` if the health endpoint never
        comes up before the timeout.
    '''
    args = _build_arg_parser().parse_args(argv)
    _ensure_host_only()

    if args.state not in GEOFABRIK_STATE_SLUGS:
        print(
            f'Unknown state slug: {args.state!r}. Use the full Geofabrik slug, '
            f'e.g. "georgia", "new-york", "district-of-columbia". See '
            f'python/utils/ors_setup.py for the full list.'
        )
        sys.exit(2)

    os.makedirs(args.logdir, exist_ok=True)
    log_path = os.path.join(args.logdir, f'{datetime.now().strftime("%Y%m%d%H%M%S")}_ors_up.log')
    log_fh = open(log_path, 'a', encoding='utf-8')  # pylint: disable=consider-using-with  # closed in finally
    try:
        _tee(f'[{datetime.now().isoformat(timespec="seconds")}] starting ORS for {args.state}', log_fh)
        _tee(f'compose file: {COMPOSE_FILE}', log_fh)

        pbf_filesystem_path = download_pbf_if_missing(args.state)
        _tee(f'pbf: {pbf_filesystem_path}', log_fh)

        # Pre-create the per-state graph cache dir so the compose bind mount
        # resolves to a user-owned directory (Docker would otherwise auto-
        # create it as root, which then can't be modified without sudo).
        state_graphs_dir = os.path.join(ORS_GRAPHS_DIR, args.state)
        os.makedirs(state_graphs_dir, exist_ok=True)
        _tee(f'graphs dir: {state_graphs_dir}', log_fh)

        env = os.environ.copy()
        env['ORS_STATE'] = args.state
        subprocess.run(
            ['docker', 'compose', '-f', COMPOSE_FILE, 'up', '-d'],
            env=env,
            check=True,
        )
        _tee(f'polling {args.health_url} ...', log_fh)
        if not poll_health(args.health_url):
            _tee('TIMEOUT waiting for ORS health endpoint', log_fh)
            subprocess.run(
                ['docker', 'compose', '-f', COMPOSE_FILE, 'logs', '--tail=50', 'ors'],
                check=False,
            )
            sys.exit(1)

        _tee('ORS is up and routing.', log_fh)
        return 0
    finally:
        log_fh.close()


if __name__ == '__main__':
    sys.exit(main())
