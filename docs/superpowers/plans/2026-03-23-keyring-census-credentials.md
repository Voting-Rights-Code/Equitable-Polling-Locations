# Keyring-Based Census API Key Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Python-module import of the census API key with OS keychain storage (via `keyring`) and a JSON bridge file for Docker access.

**Architecture:** `run.py` gains two new capabilities: a `set_census_key` subcommand that stores the key in the OS keychain via `keyring`, and a `-k` flag that writes the key from keyring to `authentication_files/credentials.json` before launching Docker. Inside Docker, `pull_census_data.py` reads the JSON file instead of importing a Python module.

**Tech Stack:** Python 3, `keyring` (host-side only), `json` (stdlib)

**Spec:** `docs/superpowers/specs/2026-03-23-keyring-census-credentials-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `python/utils/pull_census_data.py` | Modify | Replace module import with `_load_census_key()` JSON reader |
| `python/tests/pull_census_key_test.py` | Create | Unit tests for `_load_census_key()` and `pull_census_data()` ValueError |
| `python/tests/write_credentials_test.py` | Create | Unit test for `write_credentials_json()` |
| `run.py` | Modify | Add `set_census_key` subcommand and `-k` flag (both pre-argparse interceptions) |
| `docs/input_files.md` | Modify | Replace old census key setup instructions with keyring workflow |
| `docs/to_install.md` | Modify | Add `pip install keyring` prerequisite and census key setup docs |

**Note:** No top-level `README.md` exists. `docs/README.md` does not reference census_key or authentication_files, so no README changes are needed.

---

### Task 1: Add `_load_census_key()` to `pull_census_data.py` (TDD)

**Files:**
- Create: `python/tests/pull_census_key_test.py`
- Modify: `python/utils/pull_census_data.py`

- [ ] **Step 1: Write failing tests for `_load_census_key()`**

Create `python/tests/pull_census_key_test.py`:

```python
"""Tests for census key loading from credentials.json."""

import json
import pytest

from python.utils.pull_census_data import _load_census_key


class TestLoadCensusKey:
    """Tests for _load_census_key()."""

    def test_returns_key_when_valid_json(self, tmp_path):
        """Valid JSON with census_key field returns the key string."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"census_key": "test-key-123"}))
        result = _load_census_key(creds_file)
        assert result == "test-key-123"

    def test_returns_none_when_file_missing(self, tmp_path):
        """Missing file returns None."""
        creds_file = tmp_path / "credentials.json"
        result = _load_census_key(creds_file)
        assert result is None

    def test_returns_none_when_malformed_json(self, tmp_path):
        """Malformed JSON returns None."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("not valid json{{{")
        result = _load_census_key(creds_file)
        assert result is None

    def test_returns_none_when_key_field_absent(self, tmp_path):
        """Valid JSON without census_key field returns None."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"other_key": "value"}))
        result = _load_census_key(creds_file)
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm app pytest python/tests/pull_census_key_test.py -v`

Expected: FAIL — `ImportError: cannot import name '_load_census_key'`

- [ ] **Step 3: Implement `_load_census_key()` in `pull_census_data.py`**

In `python/utils/pull_census_data.py`, replace lines 1-12 (the import block):

```python
# Old code to remove:
# import os
# from pathlib import Path
# import shutil
# import requests
# import subprocess
# import argparse
# import pandas as pd
#
# try:
#     from authentication_files.census_key import census_key
# except:
#     census_key = None
```

With:

```python
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

import pandas as pd
import requests


CREDENTIALS_PATH = Path(__file__).resolve().parent.parent.parent / "authentication_files" / "credentials.json"


def _load_census_key(credentials_path=CREDENTIALS_PATH):
    """Load the census API key from the credentials JSON file.

    Args:
        credentials_path: Path to the credentials JSON file.
            Defaults to authentication_files/credentials.json at the project root.

    Returns:
        The census API key string, or None if the file is missing,
        malformed, or does not contain a 'census_key' field.
    """
    try:
        with open(credentials_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("census_key")
    except (FileNotFoundError, json.JSONDecodeError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm app pytest python/tests/pull_census_key_test.py -v`

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python/tests/pull_census_key_test.py python/utils/pull_census_data.py
git commit -m "feat: add _load_census_key() to read census key from JSON credentials file"
```

---

### Task 2: Update `pull_census_data()` to use `_load_census_key()` (TDD)

**Files:**
- Modify: `python/tests/pull_census_key_test.py`
- Modify: `python/utils/pull_census_data.py`

- [ ] **Step 1: Write failing test for ValueError behavior**

Append to `python/tests/pull_census_key_test.py`:

```python
from unittest.mock import patch

from python.utils.pull_census_data import pull_census_data


class TestPullCensusDataKeyHandling:
    """Tests for pull_census_data() census key resolution."""

    @patch("python.utils.pull_census_data._load_census_key", return_value=None)
    def test_raises_valueerror_when_no_key_available(self, _mock_loader):
        """pull_census_data raises ValueError when no apikey is provided and loader returns None."""
        # state_lookup={} is safe — ValueError fires before state_lookup is used
        with pytest.raises(ValueError, match="No census key available"):
            pull_census_data("GA", "Gwinnett County", apikey=None, state_lookup={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm app pytest python/tests/pull_census_key_test.py::TestPullCensusDataKeyHandling -v`

Expected: The test may pass or fail depending on whether the old `census_key` module-level variable is still used as the default. If it passes, the next step still needs to be done to clean up the signature.

- [ ] **Step 3: Update `pull_census_data()` signature and body**

In `python/utils/pull_census_data.py`, find the function definition `def pull_census_data(statecode, county, apikey = census_key, state_lookup=STATE_LOOKUP):` (originally at line 208, but shifted after Task 1 changes). Replace the signature and the body through the existing `raise ValueError` line with:

```python
def pull_census_data(statecode, county, apikey=None, state_lookup=STATE_LOOKUP):
    """Pull P3 and P4 census data and tiger shapefiles for a given county.

    Given a state code (e.g. 'MD' or 'NY') and county name (full name,
    properly capitalized), downloads census redistricting data and
    TIGER shapefiles.

    Args:
        statecode: Two-letter US state code.
        county: Full county name with proper capitalization.
        apikey: Census API key. If None, attempts to load from
            authentication_files/credentials.json.
        state_lookup: Mapping of state codes to full state names.

    Raises:
        ValueError: If no census API key is available.
    """
    if apikey is None:
        apikey = _load_census_key()
    if apikey is None:
        raise ValueError('No census key available. Please request one from the census to download census data. See README.')
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `docker compose run --rm app pytest python/tests/pull_census_key_test.py -v`

Expected: All 5 tests PASS

- [ ] **Step 5: Run lint**

Run: `docker compose run --rm app pylint python/utils/pull_census_data.py`

Expected: No errors (the bare `except` on the old import is gone, which should improve the lint score)

- [ ] **Step 6: Confirm `__main__` block is correct**

The `__main__` block at the bottom of `pull_census_data.py` calls `pull_census_data(args.state, args.county)` without passing `apikey`. After our changes, this correctly falls through to `_load_census_key()`, which reads `credentials.json`. No changes needed — just verify the block still works by reading the file.

- [ ] **Step 7: Commit**

```bash
git add python/utils/pull_census_data.py python/tests/pull_census_key_test.py
git commit -m "feat: pull_census_data() loads census key from credentials.json instead of Python module import"
```

---

### Task 3: Add `set_census_key` subcommand and `write_credentials_json()` to `run.py` (TDD)

**Files:**
- Create: `python/tests/write_credentials_test.py`
- Modify: `run.py`

- [ ] **Step 1: Write failing test for `write_credentials_json()`**

Create `python/tests/write_credentials_test.py`:

```python
"""Tests for write_credentials_json() in run.py."""

import json
import pytest

from run import write_credentials_json


class TestWriteCredentialsJson:
    """Tests for write_credentials_json()."""

    def test_writes_valid_json_with_census_key(self, tmp_path):
        """Creates credentials.json with the correct structure."""
        write_credentials_json("test-key-abc", output_dir=tmp_path)
        creds_file = tmp_path / "credentials.json"
        assert creds_file.exists()
        data = json.loads(creds_file.read_text())
        assert data == {"census_key": "test-key-abc"}

    def test_creates_directory_if_missing(self, tmp_path):
        """Creates the output directory if it does not exist."""
        nested = tmp_path / "subdir"
        write_credentials_json("key-123", output_dir=nested)
        assert (nested / "credentials.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest python/tests/write_credentials_test.py -v`

Expected: FAIL — `ImportError: cannot import name 'write_credentials_json'`

- [ ] **Step 3: Add `write_credentials_json()` and `set_census_key` to `run.py`**

In `run.py`, add `getpass` and `json` imports at the top (after `from pathlib import Path`):

```python
import getpass
import json
```

Add the new helper function between `get_scripts()` and `main()`:

```python
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
```

Add the `set_census_key` interception in `main()`, after the `e2e_tests` block (after its `return` statement), before `available_scripts = get_scripts()`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest python/tests/write_credentials_test.py -v`

Expected: All 2 tests PASS

- [ ] **Step 5: Test `set_census_key` manually**

Run: `python run.py set_census_key`

Expected: Prompts for the census key (input hidden), prints confirmation message. Verify with: `python -c "import keyring; print(keyring.get_password('equitable-polling', 'census_key'))"`

- [ ] **Step 6: Commit**

```bash
git add run.py python/tests/write_credentials_test.py
git commit -m "feat: add write_credentials_json() and set_census_key subcommand"
```

---

### Task 4: Add `-k` flag to `run.py`

**Files:**
- Modify: `run.py`

- [ ] **Step 1: Add `-k` flag interception before argparse**

In `run.py`, add the `-k` flag interception in the `main()` function, right after the `set_census_key` block and before `available_scripts = get_scripts()`. This intercepts `-k`/`--keyring` from `sys.argv` before argparse sees it:

```python
    # Flag: -k / --keyring populates credentials.json from the OS keychain
    use_keyring = False
    if '-k' in sys.argv or '--keyring' in sys.argv:
        use_keyring = True
        # Remove the flag so argparse doesn't see it
        sys.argv = [a for a in sys.argv if a not in ('-k', '--keyring')]

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
```

- [ ] **Step 2: Update the argparse help text**

Update the `ArgumentParser` description (around line 51) to mention the `-k` flag:

```python
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
```

- [ ] **Step 3: Test manually**

Run: `python run.py -k model_run_cli -c 1 -l ./datasets/configs/Gwinnett_GA/config.yaml` (or any valid script invocation)

Expected: Reads key from keyring, writes `authentication_files/credentials.json`, then proceeds with Docker. Verify the JSON file exists and contains the key.

- [ ] **Step 4: Run lint on run.py**

Run: `pylint run.py`

Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add run.py
git commit -m "feat: add -k flag to populate census credentials from OS keychain before Docker run"
```

---

### Task 5: Update documentation

**Files:**
- Modify: `docs/input_files.md:129-136`
- Modify: `docs/to_install.md`

- [ ] **Step 1: Update `docs/input_files.md`**

Keep the heading `## **Census Data (demographics and shapefiles)**:` on line 129. Replace lines 130-136 (from "The sofware requires..." through "...data does not exist locally."):

```markdown
The sofware requires a free census API key to run new counties. You can [apply on the cenus site](https://api.census.gov/data/key_signup.html) and be approved in seconds.

    1. Create the directory authentication_files/
    2. Inside authentication_files/ create a file called census_key.py
    3. The file should have a single line reading: census_key = "YOUR_KEY_VALUE"

If you are only running counties already in the repo you skip this step. However, it is needed to run counties for which data does not exist locally.
```

With:

```markdown
The software requires a free census API key to run new counties. You can [apply on the census site](https://api.census.gov/data/key_signup.html) and be approved in seconds.

To store your census API key securely using the OS keychain:

    1. Install keyring: pip install keyring
    2. Store your key: python run.py set_census_key
    3. When running a script that needs census data, use the -k flag:
       python run.py -k <script> [args]

The -k flag writes a cached copy of the key to authentication_files/credentials.json (gitignored). After the first use of -k, subsequent runs will use the cached file automatically without needing -k.

If you are only running counties already in the repo you can skip this step. However, it is needed to run counties for which data does not exist locally.
```

- [ ] **Step 2: Update `docs/to_install.md`**

Add a new section between the "Installation" steps and "### Test the Installation". Insert after the blank line following line 14 (`Additional environments may be configured as necessary.`) and before line 17 (`### Test the Installation`):

```markdown
### Census API Key (optional, for new counties)

If you plan to download census data for counties not already in the repo, you need a free census API key.

1. [Apply for a census API key](https://api.census.gov/data/key_signup.html) (approved in seconds)
2. Install keyring on your host machine: `pip install keyring`
3. Store your key: `python run.py set_census_key`
4. Use `-k` when running scripts that need census data: `python run.py -k <script> [args]`

The `-k` flag caches the key locally in `authentication_files/credentials.json` (gitignored), so you only need to pass `-k` once. Subsequent runs will use the cached file.
```

- [ ] **Step 3: Commit**

```bash
git add docs/input_files.md docs/to_install.md
git commit -m "docs: update census key setup instructions for keyring-based workflow"
```

---

### Task 6: Run full test suite and final lint

**Files:** None (verification only)

- [ ] **Step 1: Run full unit test suite**

Run: `docker compose run --rm app pytest`

Expected: All tests PASS. The removal of the old `from authentication_files.census_key import census_key` import should not break anything since `_load_census_key()` returns `None` gracefully when no credentials file exists.

- [ ] **Step 2: Run lint**

Run: `docker compose run --rm app pylint python/`

Expected: No new errors. The bare `except:` on the old import (line 11) is gone, which should improve the lint score.

- [ ] **Step 3: Run CSV e2e tests**

Run: `python run.py e2e_tests -m e2e_csv`

Expected: All CSV e2e tests PASS (these don't use census data download)
