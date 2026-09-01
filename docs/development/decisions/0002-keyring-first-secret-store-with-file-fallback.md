# 0002: Manage API credentials with a keyring-first secret store and a gitignored file fallback

## Status

Accepted

## Context

The project needs third-party API credentials at runtime: a Census API key, and — for CVAP configurations — a Redistricting Data Hub (RDH) username and password. These credentials have awkward, competing requirements:

- They must be available **on the host** (where contributors launch `run.py`), **inside the dev/app container** (where the solver and the census/CVAP data pulls actually run), and **in CI**.
- They must **never be committed** to git.
- They should **survive `git clean -fdx`** (a common reset in this project), so re-entering them constantly is avoided.

No single storage mechanism satisfies all of these:

- An **OS keyring** is secure and durable, but it is host-only, is not installed by default (and is fiddly to install for the right interpreter, e.g. PEP 668 on macOS), and is unavailable inside the container.
- A **plain JSON file** is portable (works in-container with no dependencies) but is wiped by `git clean -fdx` and must be carefully gitignored.
- **Environment variables** are trivial for CI/containers but are not durable and are easy to leak into shell history.

The earlier approach loaded the Census key from an imported Python module, which forced contributors to edit code and risked committing the key.

## Decision

Introduce a small **secret registry** (`secret_store.py`, repo root, host-importable, stdlib + optional `keyring`). Each secret declares: a name, an OS-keyring service/username, an environment variable, and a field in a gitignored `authentication_files/credentials.json`. Each secret also carries a `sensitive` flag (so a non-secret value like an RDH *username* can be shown while a password is masked), and related secrets can be grouped (e.g. the `rdh` group = `rdh_username` + `rdh_password`).

A `run.py secret set | get | clear | restore` CLI manages them:

- **`set`** writes to **both** the OS keyring (when installed) and `credentials.json` (dual-write).
- Runtime **resolution precedence is environment variable > OS keyring > `credentials.json`**.
- Host-launched `run.py` **forwards** each resolved secret into the container as a name-only `-e VAR` flag, so in-container code sees it as an env var; the bind-mounted `credentials.json` is the in-container fallback (the keyring is host-only).
- **`restore`** rebuilds `credentials.json` from the keyring after `git clean -fdx`.

Alternatives considered and rejected as a *sole* mechanism: env-vars-only (not durable, leak-prone — kept only as the highest-precedence override for CI/containers); a committed encrypted file (key-management burden, still leak-prone); keyring-only (host-only, not always installed, unavailable in-container); file-only (wiped by `git clean -fdx`, no OS-level protection). The layered design combines the keyring's durability, the file's portability, and the env var's CI-friendliness while keeping secrets out of git.

## Consequences

- New credentials plug in by adding one registry entry — host forwarding, keyring/file storage, and the CLI all work generically. (CVAP's RDH username/password were added this way, on top of the original Census-only design, with no changes to the core resolve/store/forward logic.)
- Contributors run `run.py secret set <name>` once per machine; without `keyring` installed the file fallback still works but is wiped by `git clean -fdx` (recover with `run.py secret restore` if keyring is present, otherwise re-run `secret set`).
- `keyring` is optional but recommended as a durable backup; nothing breaks without it.
- **Out of scope:** access to Google Cloud / BigQuery uses Google **Application Default Credentials** (`gcloud auth application-default login`), which is a separate mechanism from this secret store. See CONTRIBUTING.md → Database Setup.
