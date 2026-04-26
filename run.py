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

def get_scripts() -> list[str]:
    """Dynamically finds available scripts in ./python/scripts."""
    scripts_dir = Path(__file__).resolve().parent / "python" / "scripts"
    if not scripts_dir.exists():
        return []
    # Returns sorted filenames without the .py extension
    return sorted([f.stem for f in scripts_dir.glob("*.py")])

def main():
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
    env = os.environ.copy()
    env["GCP_CREDS_PATH"] = get_gcp_creds_path()

    # 3. Construct and Run Docker Command
    # Using 'python -m' ensures internal package imports work correctly
    cmd = [
        "docker", "compose", "run", "--rm", "app",
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
