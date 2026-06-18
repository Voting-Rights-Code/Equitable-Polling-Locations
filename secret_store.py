"""Host-side secret store.

Stores secrets in `authentication_files/credentials.json` and, when `keyring` is
available, additionally in the OS keystore as a durable backup. Stdlib-only (plus
an optional `keyring` import) so it is importable from the zero-setup host `run.py`
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
    """Describes one named secret and where it is stored / read from.

    Attributes:
        name: Short identifier used to look the secret up in SECRETS.
        keyring_service: Service name passed to the OS keystore.
        keyring_username: Username key passed to the OS keystore.
        env_var: Environment variable that overrides all stored values.
        file_path: Absolute path to the JSON credentials file fallback.
        file_field: JSON key under which the value is stored in file_path.
    """

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
    """Return the registered Secret descriptor for the given name.

    Args:
        name: Short identifier for the secret (e.g. ``"census"``).

    Returns:
        The Secret dataclass registered under that name.

    Raises:
        KeyError: When name is not present in the SECRETS registry.
    """
    return SECRETS[name]


def _read_file(secret: Secret) -> Optional[str]:
    """Return the secret value from the JSON credentials file.

    Args:
        secret: The Secret whose file_path and file_field to read.

    Returns:
        The stored string value, or None if the file is absent, unreadable,
        or does not contain the expected field.
    """
    try:
        with open(secret.file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get(secret.file_field)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_file(secret: Secret, value: str) -> None:
    """Write the secret value into the JSON credentials file.

    Existing fields in the file are preserved; only the secret's own field is
    updated.  The parent directory is created if it does not already exist.

    Args:
        secret: The Secret whose file_path and file_field to write.
        value: The plaintext secret value to store.

    Returns:
        None
    """
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
    """Remove the secret's field from the JSON credentials file.

    When removing the field leaves the file empty, the file itself is deleted.

    Args:
        secret: The Secret whose file_path and file_field to clear.

    Returns:
        True if the field was present and removed; False if the file was
        missing, malformed, or did not contain the field.
    """
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
    """Return True when the keyring module was successfully imported.

    A present-but-unusable backend (e.g. no daemon running) is not detected
    here; it surfaces as a KeyringError at call time inside _read_keyring,
    _store_keyring, or _clear_keyring, where it is handled gracefully.

    Returns:
        True if keyring was importable; False if the import failed.
    """
    return keyring is not None


def _read_keyring(secret: Secret) -> Optional[str]:
    """Return the secret value from the OS keystore.

    Args:
        secret: The Secret whose keyring_service and keyring_username to query.

    Returns:
        The stored string value, or None if keyring is not installed, the
        entry does not exist, or the backend raises KeyringError.
    """
    if keyring is None:
        return None
    try:
        return keyring.get_password(secret.keyring_service, secret.keyring_username)
    except KeyringError:
        return None


def _store_keyring(secret: Secret, value: str) -> None:
    """Store the secret value in the OS keystore.

    This function is only ever called from store() after confirming that
    keyring is not None, so no module-presence guard is needed here.

    Args:
        secret: The Secret whose keyring_service and keyring_username to use.
        value: The plaintext secret value to store.

    Returns:
        None

    Raises:
        KeyringError: When the OS keystore backend is present but unusable.
            The caller (store()) catches this; the credentials file is written regardless.
    """
    keyring.set_password(secret.keyring_service, secret.keyring_username, value)


def _clear_keyring(secret: Secret) -> bool:
    """Delete the secret from the OS keystore.

    Args:
        secret: The Secret whose keyring_service and keyring_username to delete.

    Returns:
        True if the entry was found and deleted; False if keyring is not
        installed, the entry was absent, or the backend raised KeyringError.
    """
    if keyring is None:
        return False
    try:
        keyring.delete_password(secret.keyring_service, secret.keyring_username)
        return True
    except KeyringError:
        return False


def resolve(secret: Secret) -> Optional[str]:
    """Resolve the secret value using a fixed precedence chain.

    Checks sources in order: environment variable, then OS keystore, then the
    JSON credentials file.  An empty environment variable (``""``) is treated
    as absent and falls through to the next source.

    Args:
        secret: The Secret to resolve.

    Returns:
        The first non-empty value found, or None if all sources are absent.
    """
    env_value = os.environ.get(secret.env_var)
    if env_value:
        return env_value
    keyring_value = _read_keyring(secret)
    if keyring_value:
        return keyring_value
    return _read_file(secret)


def store(secret: Secret, value: str) -> list[str]:
    """Store the secret in every available backend.

    Always writes the JSON credentials file; additionally writes the OS keystore
    when keyring is installed and its backend is usable. Writing both lets a
    single host-side ``secret set`` reach host-launched runs (via keyring or
    file) and the bind-mounted credentials.json that the dev container reads.

    Args:
        secret: The Secret to store.
        value: The plaintext secret value to persist.

    Returns:
        The backends written, e.g. ``["keyring", "file"]`` or ``["file"]``.
    """
    backends: list[str] = []
    if keyring is not None:
        try:
            _store_keyring(secret, value)
            backends.append("keyring")
        except KeyringError:
            pass
    _write_file(secret, value)
    backends.append("file")
    return backends


def clear(secret: Secret) -> list[str]:
    """Remove the secret from every backend where it is stored.

    Args:
        secret: The Secret to clear.

    Returns:
        A list of backend names that were cleared (e.g. ``["keyring", "file"]``).
        Returns an empty list when the secret was not found in any backend.
    """
    removed = []
    if _clear_keyring(secret):
        removed.append("keyring")
    if _clear_file(secret):
        removed.append("file")
    return removed


def mask(value: str) -> str:
    """Return a masked form of the value safe for display in logs.

    Args:
        value: The plaintext secret value to mask.

    Returns:
        A string of the form ``"****XXXX"`` where XXXX is the last 4
        characters of value, or ``"****"`` when value has 4 or fewer
        characters.
    """
    if len(value) > 4:
        return "****" + value[-4:]
    return "****"
