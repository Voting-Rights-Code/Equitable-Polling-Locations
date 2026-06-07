"""Host-side secret store.

Stores secrets in the OS keystore via `keyring` when available, falling back to
`authentication_files/credentials.json` when it is not. Stdlib-only (plus an
optional `keyring` import) so it is importable from the zero-setup host `run.py`
as well as from inside the container.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import keyring  # optional host-only dependency
    from keyring.errors import KeyringError
except ImportError:
    keyring = None

    class KeyringError(Exception):
        """Stand-in used when `keyring` is not installed, so call sites can
        catch a consistent exception type regardless of availability."""


REPO_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Secret:
    """Describes one named secret and where it is stored / read from."""

    name: str
    keyring_service: str
    keyring_username: str
    env_var: str
    file_path: Path
    file_field: str


SECRETS: dict[str, Secret] = {
    "census": Secret(
        name="census",
        keyring_service="equitable-polling-locations",
        keyring_username="census_api_key",
        env_var="CENSUS_API_KEY",
        file_path=REPO_ROOT / "authentication_files" / "credentials.json",
        file_field="census_key",
    ),
}


def get_secret(name: str) -> Secret:
    """Return the registered Secret for `name`, raising KeyError if unknown."""
    return SECRETS[name]


def _read_file(secret: Secret) -> Optional[str]:
    """Return the secret value from its JSON file, or None if unavailable."""
    try:
        with open(secret.file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get(secret.file_field)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_file(secret: Secret, value: str) -> None:
    """Write the secret value into its JSON file, preserving other fields."""
    secret.file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(secret.file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data[secret.file_field] = value
    with open(secret.file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def _clear_file(secret: Secret) -> bool:
    """Remove the secret's field from its file. Delete the file if it becomes
    empty. Return True if anything was removed."""
    try:
        with open(secret.file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    if secret.file_field not in data:
        return False
    del data[secret.file_field]
    if data:
        with open(secret.file_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    else:
        secret.file_path.unlink()
    return True


def keyring_available() -> bool:
    """Return True if the keyring module imported. A present-but-unusable backend
    surfaces as a KeyringError at call time and is handled there (file fallback)."""
    return keyring is not None


def _read_keyring(secret: Secret) -> Optional[str]:
    """Return the secret from the OS keystore, or None if unavailable/erroring."""
    if keyring is None:
        return None
    try:
        return keyring.get_password(secret.keyring_service, secret.keyring_username)
    except KeyringError:
        return None


def _store_keyring(secret: Secret, value: str) -> None:
    """Store the secret in the OS keystore. Raises KeyringError if the backend
    is unusable (caller falls back to the file)."""
    keyring.set_password(secret.keyring_service, secret.keyring_username, value)


def _clear_keyring(secret: Secret) -> bool:
    """Delete the secret from the OS keystore. Return True if one was removed."""
    if keyring is None:
        return False
    try:
        keyring.delete_password(secret.keyring_service, secret.keyring_username)
        return True
    except KeyringError:
        return False


def resolve(secret: Secret) -> Optional[str]:
    """Resolve the secret value: env var > keyring > file > None."""
    env_value = os.environ.get(secret.env_var)
    if env_value:
        return env_value
    keyring_value = _read_keyring(secret)
    if keyring_value:
        return keyring_value
    return _read_file(secret)


def store(secret: Secret, value: str) -> str:
    """Store the secret. Prefer the OS keystore; fall back to the file if keyring
    is absent or its backend is unusable. Return "keyring" or "file"."""
    if keyring is not None:
        try:
            _store_keyring(secret, value)
            return "keyring"
        except KeyringError:
            pass
    _write_file(secret, value)
    return "file"


def clear(secret: Secret) -> list[str]:
    """Remove the secret from every backend. Return the backends cleared."""
    removed = []
    if _clear_keyring(secret):
        removed.append("keyring")
    if _clear_file(secret):
        removed.append("file")
    return removed


def mask(value: str) -> str:
    """Return a masked form of the value showing at most the last 4 characters."""
    if len(value) > 4:
        return "****" + value[-4:]
    return "****"
