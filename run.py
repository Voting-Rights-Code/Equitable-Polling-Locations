"""
Convenient entry point for running Python scripts in Docker.
Detects host OS for GCP paths and passes them to Docker Compose.
"""

import argparse
import getpass
import json
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
    with open(creds_file, 'w', encoding='utf-8') as f:
        json.dump({"census_key": census_key}, f)
    print(f"Credentials written to {creds_file}")


def main():
    # Special command: e2e_tests bypasses script discovery and runs pytest
    if len(sys.argv) > 1 and sys.argv[1] == 'e2e_tests':
        env = os.environ.copy()
        env["GCP_CREDS_PATH"] = get_gcp_creds_path()
        extra_args = sys.argv[2:]
        cmd = [
            "docker", "compose", "run", "--rm", "app",
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

    # Special command: set_census_key stores a census API key in the OS keychain
    if len(sys.argv) > 1 and sys.argv[1] == 'set_census_key':
        try:
            import keyring
        except ImportError:
            print("Error: 'keyring' package is not installed.")
            print("Install it with: pip install keyring")
            sys.exit(1)
        key = getpass.getpass("Enter your census API key: ")
        if not key.strip():
            print("Error: No key entered.")
            sys.exit(1)
        try:
            keyring.set_password("equitable-polling", "census_key", key.strip())
        except Exception as e:
            print(f"Error: Failed to store key in OS keychain: {e}")
            print("Check that your system has a supported keyring backend.")
            sys.exit(1)
        print("Census API key stored in OS keychain.")
        return

    # Flag: -k / --keyring populates credentials.json from the OS keychain.
    # Remove only the first occurrence to avoid stripping -k from forwarded script args.
    use_keyring = False
    idx = next((i for i, a in enumerate(sys.argv) if a in ('-k', '--keyring')), None)
    if idx is not None:
        use_keyring = True
        sys.argv = sys.argv[:idx] + sys.argv[idx + 1:]

    if use_keyring:
        try:
            import keyring
        except ImportError:
            print("Error: 'keyring' package is not installed.")
            print("Install it with: pip install keyring")
            sys.exit(1)
        try:
            key = keyring.get_password("equitable-polling", "census_key")
        except Exception as e:
            print(f"Error: Failed to read from OS keychain: {e}")
            print("Check that your system has a supported keyring backend.")
            sys.exit(1)
        if key is None:
            print("Error: No census API key found in OS keychain.")
            print("Run 'python run.py set_census_key' first to store your key.")
            sys.exit(1)
        write_credentials_json(key)

    available_scripts = get_scripts()

    script_list = "\n  ".join(available_scripts)

    # 1. Initialize Argparse (Native Library)
    parser = argparse.ArgumentParser(
        prog="python run.py",
        description=(
            "Run solver related python scripts inside the Docker container.\n\n"
            "Use -k before the script name to populate census credentials from\n"
            "the OS keychain (via keyring). The credentials are cached locally in\n"
            "authentication_files/credentials.json so -k is only needed once.\n\n"
            "Special commands:\n"
            "  set_census_key  Store your census API key in the OS keychain\n"
            "  e2e_tests       Run end-to-end tests"
        ),
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
