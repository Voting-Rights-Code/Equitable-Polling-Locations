"""
Convenient entry point for running project commands.

When invoked from the host, wraps commands in ``docker compose run --rm app``
against the dev container image. When invoked from inside the dev container
(detected via ``/.dockerenv``), runs the same commands directly — the conda
env is already active on PATH, so no Docker wrapper is needed. Either way,
the command-line interface is identical.
"""

import argparse
import subprocess
import sys
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
            "  test        Run the full pytest suite (unit + e2e)\n"
            "  e2e_tests   Run end-to-end tests only (e.g. python run.py e2e_tests -m e2e_csv)\n"
            "  lint        Run pylint against python/ (e.g. python run.py lint --errors-only)\n"
            "  r_test      Run the R environment smoke test\n"
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
