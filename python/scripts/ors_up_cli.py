'''CLI: bring up the sibling ORS container and wait for it to become routable.

After ``docker compose up -d`` the ORS API needs several minutes on first boot
to build its routing graph. This script polls the health endpoint until it
returns 200 or the timeout expires, dumping container logs on timeout so the
operator can diagnose.

Host-only.
'''
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

import requests

from python.scripts.ors_setup_cli import ensure_host_only
from python.utils.utils import log_date_prefix


HEALTH_POLL_INTERVAL_S = 10
HEALTH_POLL_TIMEOUT_S = 900   # 15 minutes.
DEFAULT_HEALTH_URL = 'http://localhost:8080/ors/v2/health'
COMPOSE_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', '.devcontainer', 'docker-compose.ors.yml',
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
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True
        except (requests.RequestException, ConnectionError):
            pass
        time.sleep(poll_interval_s)
    return False


def _tee(message: str, log_fh) -> None:
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
        description='Start the sibling ORS container and wait for it to be ready.',
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
    ensure_host_only()

    os.makedirs(args.logdir, exist_ok=True)
    log_path = os.path.join(args.logdir, f'{log_date_prefix()}_ors_up.log')
    log_fh = open(log_path, 'a', encoding='utf-8')   # pylint: disable=consider-using-with  # closed in finally below
    try:
        _tee(f'[{datetime.now().isoformat(timespec="seconds")}] starting ORS', log_fh)
        _tee(f'compose file: {COMPOSE_FILE}', log_fh)
        subprocess.run(
            ['docker', 'compose', '-f', COMPOSE_FILE, 'up', '-d'],
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
