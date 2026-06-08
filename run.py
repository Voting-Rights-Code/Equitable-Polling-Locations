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
    """Prompt for and store a secret value.

    Args:
        secret: The registry entry describing where to store the value.
    """
    prompt = f"Enter value for '{secret.name}': "
    if secret.sensitive:
        value = getpass.getpass(prompt).strip()
    else:
        value = input(prompt).strip()
    if not value:
        print("Error: No value entered.")
        sys.exit(1)
    where = secret_store.store(secret, value)
    if where == "keyring":
        print(f"'{secret.name}' stored in the OS keystore.")
    else:
        print(f"'{secret.name}' written to {secret.file_path}.")
        if not secret_store.keyring_available():
            print(
                "Note: 'keyring' is not installed, so this value lives in a "
                "gitignored file that `git clean -fdx` will delete. Install it "
                "with `pip install keyring` (Linux may also need a Secret "
                "Service backend) for storage that survives working-tree wipes."
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
    reveal = show or not secret.sensitive
    shown = value if reveal else secret_store.mask(value)
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


def secrets_for_name(name: str) -> list[secret_store.Secret]:
    """Expand a CLI name into one or more secrets.

    A group name expands to its member secrets; any other name resolves to the
    single secret registered under it.

    Args:
        name: A secret name or a group name.

    Returns:
        The list of secrets the command should act on, in order.
    """
    if name in secret_store.GROUPS:
        return [secret_store.get_secret(member) for member in secret_store.GROUPS[name]]
    return [secret_store.get_secret(name)]


def handle_secret_command(argv: list[str]) -> None:
    """Parse and dispatch `run.py secret <action> <name> [--show]`.

    Args:
        argv: The argument list following the `secret` subcommand.
    """
    parser = argparse.ArgumentParser(prog="python run.py secret")
    parser.add_argument("action", choices=["set", "get", "clear"])
    parser.add_argument("name", choices=sorted(set(secret_store.SECRETS) | set(secret_store.GROUPS)))
    parser.add_argument("--show", action="store_true",
                        help="Reveal the raw value (get only).")
    args = parser.parse_args(argv)
    for secret in secrets_for_name(args.name):
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
            "  secret          Manage secrets (set/get/clear); e.g. python run.py secret set census\n"
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
