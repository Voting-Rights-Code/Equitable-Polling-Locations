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
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import secret_store


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

    Inside the dev container, executes ``args`` directly. On the host, wraps
    them in ``docker compose run`` and forwards resolved secrets into the
    container via name-only ``-e`` flags so they never appear on the command
    line.

    Args:
        args: The command and arguments to execute.
    """
    if IN_CONTAINER:
        cmd = args
        env = None
    else:
        secret_env, secret_flags = build_secret_env_and_flags()
        env = secret_env
        cmd = (
            get_docker_compose_cmd()
            + ["-f", COMPOSE_FILE, "run", "--rm"]
            + secret_flags
            + ["app"]
            + args
        )
    try:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True, env=env)
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
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


def secret_set(secret: secret_store.Secret) -> None:
    """Prompt for and store a secret value in every available backend.

    Args:
        secret: The registry entry describing where to store the value.
    """
    value = getpass.getpass(f"Enter value for '{secret.name}': ").strip()
    if not value:
        print("Error: No value entered.")
        sys.exit(1)
    backends = secret_store.store(secret, value)
    written = []
    if "keyring" in backends:
        written.append("the OS keystore")
    if "file" in backends:
        written.append(str(secret.file_path))
    print(f"'{secret.name}' stored in: {', '.join(written)}.")
    if "keyring" not in backends:
        print(
            "Note: 'keyring' is not installed, so this value lives only in a "
            "gitignored file that `git clean -fdx` will delete. Install it "
            "with `pip install keyring` (Linux may also need a Secret "
            "Service backend) for a durable backup that survives working-tree wipes."
        )


def secret_get(secret: secret_store.Secret, show: bool) -> None:
    """Report a secret's presence and (masked or revealed) value.

    Args:
        secret: The registry entry to resolve.
        show: When True, print the raw value instead of a masked form.
    """
    value = secret_store.resolve(secret)
    if value is None:
        print(f"{secret.name}: not set")
        return
    shown = value if show else secret_store.mask(value)
    print(f"{secret.name}: present, value: {shown}")


def secret_clear(secret: secret_store.Secret) -> None:
    """Remove a secret from every backend.

    Args:
        secret: The registry entry to clear.
    """
    removed = secret_store.clear(secret)
    if removed:
        print(f"'{secret.name}' removed from: {', '.join(removed)}.")
    else:
        print(f"'{secret.name}': nothing to remove.")


def secret_restore() -> None:
    """Regenerate credentials.json from the durable source for every secret.

    Run from the host after ``git clean -fdx`` wipes the file. The keyring copy
    survives, so this rewrites credentials.json (which the dev container reads
    via the repo mount) from it.
    """
    for secret in secret_store.SECRETS.values():
        source = secret_store.restore_file(secret)
        if source is None:
            print(f"'{secret.name}': nothing to restore (no env var or keyring value).")
        else:
            print(f"'{secret.name}' restored to credentials.json (from {source}).")


def handle_secret_command(argv: list[str]) -> None:
    """Parse and dispatch `run.py secret <action> [name] [--show]`.

    Args:
        argv: The argument list following the `secret` subcommand.
    """
    parser = argparse.ArgumentParser(prog="python run.py secret")
    parser.add_argument("action", choices=["set", "get", "clear", "restore"])
    parser.add_argument("name", nargs="?", choices=sorted(secret_store.SECRETS))
    parser.add_argument("--show", action="store_true",
                        help="Reveal the raw value (get only).")
    args = parser.parse_args(argv)
    if args.action == "restore":
        secret_restore()
        return
    if args.name is None:
        parser.error("the 'name' argument is required for set/get/clear")
    secret = secret_store.get_secret(args.name)
    if args.action == "set":
        secret_set(secret)
    elif args.action == "get":
        secret_get(secret, show=args.show)
    else:
        secret_clear(secret)


def build_secret_env_and_flags() -> tuple[dict[str, str], list[str]]:
    """Resolve every registered secret for forwarding into the container.

    For each secret that resolves to a value, set it in a copy of the current
    environment and add a name-only ``-e VAR`` flag so docker forwards the value
    without exposing it on the command line.

    Returns:
        A tuple of (environment mapping for the subprocess, list of -e flags).
    """
    env = os.environ.copy()
    flags: list[str] = []
    for secret in secret_store.SECRETS.values():
        value = secret_store.resolve(secret)
        if value:
            env[secret.env_var] = value
            flags += ["-e", secret.env_var]
    return env, flags


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

    if len(sys.argv) > 1 and sys.argv[1] == "secret":
        handle_secret_command(sys.argv[2:])
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
            "  secret          Manage secrets (set/get/clear/restore); e.g. python run.py secret set census\n"
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
