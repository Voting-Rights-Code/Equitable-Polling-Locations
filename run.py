"""
Convenient entry point for running project commands.

When invoked from the host, wraps commands in ``docker compose run --rm app``
against the dev container image. When invoked from inside the dev container
(detected via ``/.dockerenv``), runs the same commands directly — the conda
env is already active on PATH, so no Docker wrapper is needed. Either way,
the command-line interface is identical.
"""

import argparse
import getpass
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


# Single source of truth for the project's Docker image. The same compose
# file drives both the dev container and host-invoked run.py commands, so
# editing environment.yml or renv.lock and rebuilding the image updates both
# workflows at once.
COMPOSE_FILE = ".devcontainer/docker-compose.yml"

# Root of the repo (where this file lives). Used as cwd when running
# commands so relative paths like "python/tests/e2e/" resolve regardless of
# where the user invokes run.py from inside the container.
REPO_ROOT = Path(__file__).resolve().parent

# /.dockerenv is created by Docker in every container it builds. Presence
# of that file is a reliable signal that run.py is already executing inside
# the project image and should skip the docker-compose wrapper.
IN_CONTAINER = Path("/.dockerenv").exists()


# These helpers live in python/utils/ors_setup.py but run.py can't use the
# normal `from python.utils.ors_setup import ...` because python/__init__.py
# imports numpy (unavailable on the host without the project conda env).
# Use importlib.util to load the file directly, mirroring the pattern in
# python/scripts/ors_up_cli.py.
def _load_ors_setup_helpers():
    """Load state_slug_from_location + location_from_config_file from disk.

    Returns:
        A 2-tuple of the two helper callables.
    """
    try:
        from python.utils.ors_setup import (  # pylint: disable=import-outside-toplevel
            location_from_config_file,
            state_slug_from_location,
        )
        return state_slug_from_location, location_from_config_file
    except ImportError:
        import importlib.util  # pylint: disable=import-outside-toplevel
        setup_path = REPO_ROOT / "python" / "utils" / "ors_setup.py"
        spec = importlib.util.spec_from_file_location("ors_setup", str(setup_path))
        if spec is None or spec.loader is None:
            raise ImportError(  # pylint: disable=raise-missing-from
                f"could not load python/utils/ors_setup.py from {setup_path}"
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.state_slug_from_location, module.location_from_config_file


# ORS lifecycle scripts must run on the host because they call
# ``docker compose`` and write to ``datasets/openrouteservice`` on the host
# filesystem. ``main`` short-circuits these to bypass the usual docker
# wrapper applied by ``run_command``.
ORS_LIFECYCLE_COMMANDS = ("ors_up_cli", "ors_down_cli")

# Host-side URL ORS exposes (compose maps host 8080 -> container 8082).
# Used by the generate_driving_distances_cli orchestration to detect whether
# ORS is already running before deciding whether to spawn / tear down.
ORS_DEFAULT_HEALTH_URL = "http://localhost:8080/ors/v2/health"


def get_docker_compose_cmd() -> list[str]:
    """Returns the docker compose command prefix for the available version.

    Prefers Docker Compose v2 (``docker compose``) and falls back to v1
    (``docker-compose``). Exits with code 1 if neither is available.

    Returns:
        The command prefix as a list, e.g. ``["docker", "compose"]`` or
        ``["docker-compose"]``.
    """
    candidates = (
        (["docker", "compose"], ["docker", "compose", "version"]),
        (["docker-compose"], ["docker-compose", "--version"]),
    )
    for prefix, probe in candidates:
        try:
            result = subprocess.run(probe, capture_output=True, check=False)
            if result.returncode == 0:
                return prefix
        except FileNotFoundError:
            continue

    print(
        "Error: Neither 'docker compose' (v2) nor 'docker-compose' (v1) is available.\n"
        "Install Docker Desktop or the docker-compose plugin and try again.",
        file=sys.stderr,
    )
    sys.exit(1)


def run_command(args: list[str]) -> None:
    """Runs a project command in whichever context run.py is executing.

    Inside the dev container, executes ``args`` directly (the conda env is
    on PATH). On the host, prepends
    ``docker compose -f .devcontainer/docker-compose.yml run --rm app``.
    Credentials (gcloud, gh, Claude) live in named docker volumes defined in
    the compose file, so no host-side credential-path plumbing is needed.

    Exit codes and Ctrl-C handling match subprocess.run with ``check=True``.
    """
    if IN_CONTAINER:
        cmd = args
    else:
        cmd = (
            get_docker_compose_cmd()
            + ["-f", COMPOSE_FILE, "run", "--rm", "app"]
            + args
        )
    try:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n[Terminated by User]")
        sys.exit(130)


def get_scripts() -> list[str]:
    """Dynamically finds available scripts in ./python/scripts."""
    scripts_dir = REPO_ROOT / "python" / "scripts"
    if not scripts_dir.exists():
        return []
    # Returns sorted filenames without the .py extension
    return sorted([f.stem for f in scripts_dir.glob("*.py")])


def write_credentials_json(census_key, output_dir=None):
    """Write the census API key to the credentials JSON bridge file.

    Args:
        census_key: The census API key string to write.
        output_dir: Directory to write credentials.json into.
            Defaults to authentication_files/ at the project root.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "authentication_files"
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    creds_file = output_dir / "credentials.json"
    with open(creds_file, "w", encoding="utf-8") as f:
        json.dump({"census_key": census_key}, f)
    print(f"Credentials written to {creds_file}")


def _config_path_from_passthrough(passthrough: list[str]) -> str | None:
    """Find the value of -l or --location-config in a passthrough argv list.

    Mirrors argparse's behavior for short flag (-l VALUE) and long flag
    (--location-config VALUE) without owning the full parser; the in-container
    script is the authoritative parser.

    Args:
        passthrough: The argv tail that survived the orchestrator's
            parse_known_args (i.e. everything other than --state /
            --keep-ors-running).

    Returns:
        The config path if found; None otherwise. Caller surfaces a usage
        error when None.
    """
    i = 0
    while i < len(passthrough):
        arg = passthrough[i]
        if arg in ("-l", "--location-config") and i + 1 < len(passthrough):
            return passthrough[i + 1]
        i += 1
    return None


def _ors_is_healthy() -> bool:
    """Probe ORS_DEFAULT_HEALTH_URL once; return True if it 200s.

    Returns:
        True if the ORS health endpoint returns 200 within a 5s timeout.
        False on any connection error, non-200 response, or timeout.
    """
    try:
        with urllib.request.urlopen(ORS_DEFAULT_HEALTH_URL, timeout=5) as response:
            return response.getcode() == 200
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


def main():
    # Special command: test runs the full pytest suite (unit + e2e).
    # Extra args are forwarded (e.g. `run.py test python/tests/e2e/`).
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_command(["pytest"] + sys.argv[2:])
        return

    # Special command: e2e_tests runs only the end-to-end subset.
    if len(sys.argv) > 1 and sys.argv[1] == "e2e_tests":
        run_command(["pytest", "python/tests/e2e/"] + sys.argv[2:])
        return

    # Special command: lint runs pylint against python/.
    # Extra args (e.g. --errors-only, a more specific path) are forwarded.
    if len(sys.argv) > 1 and sys.argv[1] == "lint":
        run_command(["pylint", "python/"] + sys.argv[2:])
        return

    # Special command: r_test runs the R environment smoke test. Confirms
    # R and all project-required R packages load inside the image.
    if len(sys.argv) > 1 and sys.argv[1] == "r_test":
        run_command(["Rscript", "R/tests/r_smoke_test.R"])
        return

    # Special command: set_census_key stores a census API key in credentials.json.
    # No external dependencies required — uses only Python stdlib.
    if len(sys.argv) > 1 and sys.argv[1] == "set_census_key":
        key = getpass.getpass("Enter your census API key: ")
        if not key.strip():
            print("Error: No key entered.")
            sys.exit(1)
        write_credentials_json(key.strip())
        print("Census API key saved to authentication_files/credentials.json")
        return

    # Special commands: ORS lifecycle scripts. These must run on the host
    # because they call docker compose / write to datasets/openrouteservice on
    # the host filesystem. Bypass the docker compose wrapper that run_command
    # would otherwise apply.
    if len(sys.argv) > 1 and sys.argv[1] in ORS_LIFECYCLE_COMMANDS:
        if IN_CONTAINER:
            print(
                f"The {sys.argv[1]} command must be run from the host "
                f"(you appear to be inside the dev container). "
                f"Open a host terminal and try again."
            )
            sys.exit(2)
        script_path = REPO_ROOT / "python" / "scripts" / f"{sys.argv[1]}.py"
        cmd = [sys.executable, str(script_path)] + sys.argv[2:]
        try:
            subprocess.run(cmd, cwd=REPO_ROOT, check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(e.returncode)
        except KeyboardInterrupt:
            print("\n[Terminated by User]")
            sys.exit(130)
        return

    # Special command: generate_driving_distances_cli auto-orchestrates ORS
    # when run from the host (spawn-and-verify via ors_up_cli, then matrix
    # inside the container via the standard wrapper, then ors_down_cli
    # cleanup unless --keep-ors-running). Inside the container, falls through
    # to the standard wrapper since ORS lifecycle is unavailable there.
    if (
        len(sys.argv) > 1
        and sys.argv[1] == "generate_driving_distances_cli"
        and not IN_CONTAINER
    ):
        # Peel out orchestrator-only flags with parse_known_args; everything
        # else (-l, --server, --logdir, etc.) is forwarded to the in-container
        # script's own argparse via `passthrough`. Watch-out: argparse
        # prefix-matches --state against any future --state-* flag; allow-list
        # if a collision ever appears.
        orchestrator_parser = argparse.ArgumentParser(add_help=False)
        orchestrator_parser.add_argument("--state", default=None)
        orchestrator_parser.add_argument(
            "--keep-ors-running", action="store_true", default=False,
        )
        orchestrator_args, passthrough = orchestrator_parser.parse_known_args(
            sys.argv[2:]
        )

        state = orchestrator_args.state
        if state is None:
            # Derive from the -l/--location-config that the in-container script
            # will receive. Read the YAML on the host (stdlib only) to avoid
            # importing PollingModelConfig (would pull numpy via python/__init__).
            config_path = _config_path_from_passthrough(passthrough)
            if config_path is None:
                print(
                    "usage: python3 run.py generate_driving_distances_cli "
                    "[--state <slug>] -l <config> [options]\n"
                    "  --state and -l/--location-config are both effectively required: "
                    "either pass --state, or pass -l so the state can be derived "
                    "from the config's location.",
                    file=sys.stderr,
                )
                sys.exit(2)
            state_slug_from_location, location_from_config_file = (
                _load_ors_setup_helpers()
            )
            try:
                location = location_from_config_file(config_path)
                state = state_slug_from_location(location)
            except ValueError as exc:
                print(
                    f"Couldn't derive state from {config_path}: {exc}.\n"
                    f"Either rename the location to end in _<ST> "
                    f"or pass an explicit override:\n"
                    f"  python3 run.py generate_driving_distances_cli "
                    f"--state georgia -l {config_path}",
                    file=sys.stderr,
                )
                sys.exit(2)

        ors_was_already_up = _ors_is_healthy()

        # Unified try/finally so an ors_up_cli failure (or matrix failure)
        # still triggers teardown when we were the ones who brought ORS up.
        # The inner try translates ors_up_cli's CalledProcessError into a
        # sys.exit so we forward its exit code; SystemExit is then caught by
        # the outer finally before propagating.
        ors_up_script = REPO_ROOT / "python" / "scripts" / "ors_up_cli.py"
        try:
            try:
                subprocess.run(
                    [sys.executable, str(ors_up_script), state],
                    cwd=REPO_ROOT,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                sys.exit(e.returncode)

            # Matrix step: forward the resolved state to the in-container
            # script via --state. This covers both the explicit-override case
            # (user passed --state for a synthetic config like `testing` whose
            # location can't be derived) and the derived case (we resolved
            # state from config.location above) — in both, the in-container
            # script should NOT re-derive. Its own derivation logic stays as
            # the fallback for direct-in-container invocations that bypass
            # run.py.
            run_command(
                ["python", "-m", "python.scripts.generate_driving_distances_cli",
                 "--state", state]
                + passthrough
            )
        finally:
            if not orchestrator_args.keep_ors_running and not ors_was_already_up:
                ors_down_script = REPO_ROOT / "python" / "scripts" / "ors_down_cli.py"
                try:
                    subprocess.run(
                        [sys.executable, str(ors_down_script)],
                        cwd=REPO_ROOT,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    print(
                        f"warning: ors_down_cli exited with {e.returncode}; "
                        f"ORS may still be running",
                        file=sys.stderr,
                    )
        return

    available_scripts = get_scripts()

    script_list = "\n  ".join(available_scripts)

    parser = argparse.ArgumentParser(
        prog="python run.py",
        description=(
            "Run solver-related project commands. Executes directly inside "
            "the dev container, or via `docker compose run --rm app` from "
            "the host."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Special commands:\n"
            "  test            Run the full pytest suite (unit + e2e)\n"
            "  e2e_tests       Run end-to-end tests only (e.g. python run.py e2e_tests -m e2e_csv)\n"
            "  lint            Run pylint against python/ (e.g. python run.py lint --errors-only)\n"
            "  r_test          Run the R environment smoke test\n"
            "  set_census_key  Store your census API key in credentials.json\n"
            "  ors_up_cli      [HOST-ONLY] Start the sibling ORS container and wait for readiness\n"
            "  ors_down_cli    [HOST-ONLY] Stop the sibling ORS container (--purge-graphs optional)\n"
            "\n"
            f"Available scripts:\n  {script_list}"
        ),
    )

    parser.add_argument(
        "script",
        choices=available_scripts,
        help="The script from ./python/scripts to run.",
    )

    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments/flags passed directly to the target script.",
    )

    # If no arguments provided, show help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # Using 'python -m' ensures internal package imports work correctly
    run_command(
        ["python", "-m", f"python.scripts.{args.script}"] + args.script_args
    )


if __name__ == "__main__":
    main()
