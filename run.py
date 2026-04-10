"""
Convenient entry point for running Python scripts in Docker.
Detects host OS for GCP paths and passes them to Docker Compose.
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

def get_gcp_creds_path():
    """Detects the host OS and returns the default gcloud config path."""
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", ""), "gcloud")
    return os.path.expanduser("~/.config/gcloud")


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

def get_scripts() -> list[str]:
    """Dynamically finds available scripts in ./python/scripts."""
    scripts_dir = Path(__file__).resolve().parent / "python" / "scripts"
    if not scripts_dir.exists():
        return []
    # Returns sorted filenames without the .py extension
    return sorted([f.stem for f in scripts_dir.glob("*.py")])

def main():
    # Special command: e2e_tests bypasses script discovery and runs pytest
    if len(sys.argv) > 1 and sys.argv[1] == 'e2e_tests':
        compose_cmd = get_docker_compose_cmd()
        env = os.environ.copy()
        env["GCP_CREDS_PATH"] = get_gcp_creds_path()
        extra_args = sys.argv[2:]
        cmd = compose_cmd + [
            "run", "--rm", "app",
            "pytest", "python/tests/e2e/"
        ] + extra_args
        try:
            subprocess.run(cmd, env=env, check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(e.returncode)
        except KeyboardInterrupt:
            print("\n[Terminated by User]")
            sys.exit(130)
        return

    available_scripts = get_scripts()

    script_list = "\n  ".join(available_scripts)

    # 1. Initialize Argparse (Native Library)
    parser = argparse.ArgumentParser(
        prog="python run.py",
        description="Run solver related python scripts inside the Docker container.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available scripts:\n  {script_list}"
    )

    # Required: The script name (validates against the actual file list)
    parser.add_argument(
        "script",
        choices=available_scripts,
        help="The script from ./python/scripts to run in the Docker container."
    )

    # Optional: Catch-all for any arguments to pass to the target script
    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments/flags passed directly to the script in the Docker container."
    )

    # If no arguments provided, show help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # 2. Prepare Environment
    compose_cmd = get_docker_compose_cmd()
    env = os.environ.copy()
    env["GCP_CREDS_PATH"] = get_gcp_creds_path()

    # 3. Construct and Run Docker Command
    # Using 'python -m' ensures internal package imports work correctly
    cmd = compose_cmd + [
        "run", "--rm", "app",
        "python", "-m", f"python.scripts.{args.script}"
    ] + args.script_args

    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n[Terminated by User]")
        sys.exit(130)

if __name__ == "__main__":
    main()
