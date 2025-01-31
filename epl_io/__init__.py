from pathlib import Path
import os

# use the environment variable, or fall back on the root of this git repo
PROJECT_ROOT = os.getenv("PROJECT_ROOT", Path(__file__).resolve().parent)
RESULT_ROOT = os.getenv("RESULT_ROOT", None)
PARTNER_DATA_ROOT = os.getenv("RESULT_ROOT", None)
LOG_FOLDER = os.getenv("LOG_FOLDER", PROJECT_ROOT.joinpath("logs"))