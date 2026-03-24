# Keyring-Based Census API Key Management

## Problem

The census API key is currently stored as a hardcoded value in `authentication_files/census_key.py` and imported via `from authentication_files.census_key import census_key`. While the file is gitignored, this pattern is fragile (importing a Python module as a config store) and doesn't leverage the OS keychain for secure credential storage.

## Solution

Replace the Python-module-based credential store with:
1. **`keyring`** as the source of truth (OS keychain, host-side only)
2. **A JSON bridge file** (`authentication_files/credentials.json`) as the Docker-accessible cache
3. **Two new `run.py` capabilities** to manage the flow

## Architecture

### Components

**`run.py` — two new capabilities:**
- `set_census_key` subcommand: intercepted via `sys.argv[1]` before argparse runs (same pattern as existing `e2e_tests`). Prompts the user for their census API key and stores it in keyring under service `"equitable-polling"`, username `"census_key"`.
- `-k` / `--keyring` flag: intercepted from `sys.argv` before argparse runs (to avoid conflict with `argparse.REMAINDER` which swallows all tokens after the script name). Usage: `python run.py -k <script> [args]`. Reads the key from keyring, writes `authentication_files/credentials.json`, then proceeds with the Docker run as normal. The JSON file persists after the run as a local cache so `-k` is not required on every subsequent invocation.

**`authentication_files/credentials.json` — bridge file:**
- Format: `{"census_key": "the-api-key-here"}`
- Already covered by `.gitignore` (which ignores the entire `authentication_files/` directory)
- Written by `run.py -k`, read inside Docker by `pull_census_data.py`

**`pull_census_data.py` — updated key loading:**
- Removes `from authentication_files.census_key import census_key` and the surrounding try/except
- Adds a private function `_load_census_key()` to load the key from `authentication_files/credentials.json`:
  - **File exists, valid JSON with `census_key` field:** returns the key string
  - **File missing:** returns `None`
  - **Malformed JSON or missing `census_key` field:** returns `None`
- `pull_census_data()` signature changes to `apikey=None` sentinel default; the function body calls `_load_census_key()` when `apikey is None` (avoids Python's import-time default evaluation)
- Falls back to `None` if the file doesn't exist or is malformed, preserving the existing `ValueError` behavior when a census pull is actually attempted without a key

**No changes to Docker:** the existing volume mount (`.:/app`) already makes the bridge file visible inside the container.

## Data Flow

```
First-time setup:
  User runs: python run.py set_census_key
  -> Prompted for API key
  -> Stored in OS keychain via keyring (service="equitable-polling", key="census_key")

Subsequent runs:
  User runs: python run.py -k <script> [args]
  -> run.py reads key from keyring
  -> Writes authentication_files/credentials.json
  -> Launches Docker as normal
  -> Inside container, pull_census_data.py reads credentials.json when needed

Without -k:
  -> run.py launches Docker as normal
  -> pull_census_data.py tries to read credentials.json
  -> If file exists (from a previous -k run): works
  -> If file doesn't exist: census_key = None -> ValueError if census pull is attempted
```

### Error Cases

- `set_census_key` with keyring backend unavailable: error with message suggesting the user check their keyring installation.
- `-k` with no key in keyring: error telling the user to run `set_census_key` first.
- No `-k` and no cached `credentials.json`: existing behavior preserved — `ValueError` at census download time with a message directing the user to request a census key.
- `credentials.json` exists but contains malformed JSON or is missing the `census_key` field: `_load_census_key()` returns `None`, falling through to the existing `ValueError` if a census pull is attempted.

## Changes by File

### Modified

**`run.py`:**
- Add `set_census_key` as a `sys.argv[1]` interception before argparse (same pattern as existing `e2e_tests`)
- Add `-k` / `--keyring` flag, intercepted from `sys.argv` before argparse runs (before the script positional arg, to avoid REMAINDER conflict)
- New helper function to write `credentials.json`
- `keyring` is a host-side dependency only (not added to Docker/conda environment); users install it via `pip install keyring`

**`pull_census_data.py`:**
- Remove `from authentication_files.census_key import census_key` and the try/except block
- Add `_load_census_key() -> str | None`: reads `authentication_files/credentials.json`, returns the `census_key` value or `None` on any failure (file missing, malformed JSON, missing field)
- Change `pull_census_data()` signature to `apikey=None` sentinel; loader called in function body when `apikey is None`
- `__main__` block unchanged

### Deprecated

**`authentication_files/census_key.py`:**
- No longer needed; replaced by `credentials.json`. The old file is gitignored and only exists locally — it was never tracked by git. Existing local copies are harmless but can be safely deleted. Setup instructions will be updated to reference the new workflow.

### Documentation Updates

**`docs/to_install.md`:**
- Document `pip install keyring` as a host-side prerequisite
- Document `python run.py set_census_key` for first-time setup
- Document `-k` flag and that `credentials.json` is cached locally after first use

**`docs/input_files.md`:**
- Replace the existing census key setup instructions (lines 132-134: "Create the directory authentication_files/", "create a file called census_key.py", etc.) with the new keyring-based workflow

**`run.py` CLI help text:**
- `-k` flag description explaining it populates credentials from keyring
- `set_census_key` help text

**`README.md`:**
- Update if it references the old `census_key.py` setup

### Unchanged

- `docker-compose.yml`
- `environment.yml`
- `.gitignore` (already covers `authentication_files/`)
- `python/utils/__init__.py` (its `from . import pull_census_data` remains unchanged; the new `_load_census_key` is private and intentionally not re-exported)

## Testing

- Unit tests for `_load_census_key()`:
  - File exists with valid JSON and `census_key` field: returns the key
  - File missing: returns `None`
  - Malformed JSON: returns `None`
  - Valid JSON but `census_key` field absent: returns `None`
- Unit test that `pull_census_data()` raises `ValueError` when no key is available (existing behavior preserved)
- No e2e test for `set_census_key` or `-k` since those depend on host keyring, which is not available in Docker
