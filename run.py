import subprocess
import sys
import os
import platform

def get_gcp_creds_path():
    """Detects the host OS and returns the correct gcloud config path."""
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("APPDATA", ""), "gcloud")
    return os.path.expanduser("~/.config/gcloud")

def main():
    # Detect GCP path for the current OS
    gcp_path = get_gcp_creds_path()

    # Base command
    # Passing the GCP path as an environment variable for docker-compose to pick up
    env = os.environ.copy()
    env["GCP_CREDS_PATH"] = gcp_path

    # Construct the full docker command
    # Sys.argv[1:] passes all arguments from 'python run.py ...' to the container
    cmd = [
        "docker", "compose", "run", "--rm", "app",
        "python", "-m"
    ] + sys.argv[1:]

    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
