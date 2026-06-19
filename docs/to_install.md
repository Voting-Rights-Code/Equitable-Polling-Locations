## Installation
1. Clone main branch of Equitable-Polling-Locations
    1. This repo uses lfs. This can be downloaded from [https://git-lfs.com/](https://git-lfs.com/).
        1. Download the appropriate version from this website and follow the instructions included there.
        1. If those instructions don't work, (as may be the case on Linux or MacOS), run ```sudo ./install.sh``` after downloading the file, then follow the instructions above. See [here](https://stackoverflow.com/questions/58796472/git-lfs-is-not-a-git-command-on-macos).
1. Install Docker from [https://www.docker.com/](https://www.docker.com/)
    1. Windows:
       1. In the Windows Subsystem for Linux set the memory to at least 8gb in the ```.wslconfig``` in the ```%USERPROFILE%``` directory.
    1. MacOS:
       1. In the docker desktop app, under resources set the memory to at least 8gb.
1. Environment settings file `settings.yaml`
    1.  The settings file allows you to configure different environments to connect to such as dev or prod, and have each environment connect to a different database or dataset.
    1.  Copy the ```settings_example.yaml``` to ```settings.yaml```
    1.  Additional environments may be configured as necessary.

### Census API Key (optional, for new counties)

If you plan to download census data for counties not already in the repo, you need a free census API key.

1. [Apply for a census API key](https://api.census.gov/data/key_signup.html) (approved in seconds)
2. Store your key (interactive prompt — no external Python packages required):
   ```bash
   python run.py secret set census
   ```

Alternatively, export the `CENSUS_API_KEY` environment variable — it takes precedence over the stored secret, which is useful inside containers and CI.

On host-launched runs, `run.py` resolves the key automatically and forwards it into the container, so no extra steps are needed beyond storing it once. (Working **inside** the dev container instead? See [Inside the dev container](#inside-the-dev-container) below.)

#### Optional: keyring backend

`secret set` always writes the value to `authentication_files/credentials.json` (gitignored), which is wiped by `git clean -fdx`.

Install `keyring` on the host to **also** store the value in your OS keystore as a durable backup that survives working-tree wipes (rebuild the file afterward with `python run.py secret restore`). It must be installed for the **same `python3` that runs `run.py`**:

```bash
pip install keyring
```

**macOS (Homebrew Python):** the command above fails with `error: externally-managed-environment` (PEP 668). Use either of these — they are equally fine:

```bash
# Option A — virtualenv (no changes to system Python); activate it before using run.py
python3 -m venv ~/.venvs/epl
source ~/.venvs/epl/bin/activate
pip install keyring

# Option B — user install, bypassing the PEP 668 guard
pip3 install --user --break-system-packages keyring
```

(`pipx` does **not** work here — it isolates *applications*, but `run.py` imports `keyring` as a *library*.) macOS Keychain support ships with the package; no extra backend is needed.

**Headless Linux** environments may also need a Secret Service backend (e.g. `pip install secretstorage`).

Nothing breaks without `keyring` — the file fallback is automatic. Verify the backend with:

```bash
python3 -c "import keyring; print(keyring.get_keyring())"
```

#### Inside the dev container

`keyring` is a host-only OS service, and `run.py` only auto-forwards secrets on host-launched runs. But `secret set` also writes `authentication_files/credentials.json`, which is in the bind-mounted repo — so a single host-side `python run.py secret set census` makes the key available **inside** the container too (the solver reads the file directly). If `git clean -fdx` removes the file, run `python run.py secret restore` on the host to rewrite it from the keyring.

### Test the Installation
To confirm the installation is setup correctly, run pytest with the following command in the root of the project directory:

```
python run.py test
```

All tests should pass.

