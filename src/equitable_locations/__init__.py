from pathlib import Path
import os

# use the environment variable, or fall back on the root of this git repo
PROJECT_ROOT = os.getenv("PROJECT_ROOT", Path(__file__).resolve().parent.parent.parent)
