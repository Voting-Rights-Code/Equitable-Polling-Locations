"""Tests for secret_store.py."""

import json

import pytest

import secret_store
from secret_store import SECRETS, Secret, get_secret, _read_file, _write_file, _clear_file, _read_keyring, _store_keyring


class TestRegistry:
    """Tests for the SECRETS registry and get_secret lookup."""
    def test_census_secret_registered(self):
        secret = get_secret("census")
        assert isinstance(secret, Secret)
        assert secret.env_var == "CENSUS_API_KEY"
        assert secret.file_field == "census_key"

    def test_unknown_secret_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_secret("nope")

    def test_census_in_registry(self):
        assert "census" in SECRETS


class TestFileBackend:
    """Tests for the file-based credential read/write/clear helpers."""
    def _secret(self, tmp_path):
        return Secret(
            name="census",
            keyring_service="svc",
            keyring_username="user",
            env_var="CENSUS_API_KEY",
            file_path=tmp_path / "authentication_files" / "credentials.json",
            file_field="census_key",
        )

    def test_write_then_read_file(self, tmp_path):
        secret = self._secret(tmp_path)
        _write_file(secret, "file-key")
        assert _read_file(secret) == "file-key"

    def test_read_missing_file_returns_none(self, tmp_path):
        assert _read_file(self._secret(tmp_path)) is None

    def test_read_malformed_file_returns_none(self, tmp_path):
        secret = self._secret(tmp_path)
        secret.file_path.parent.mkdir(parents=True)
        secret.file_path.write_text("not json{{{", encoding="utf-8")
        assert _read_file(secret) is None

    def test_clear_file_removes_field_and_empty_file(self, tmp_path):
        secret = self._secret(tmp_path)
        _write_file(secret, "file-key")
        removed = _clear_file(secret)
        assert removed is True
        assert not secret.file_path.exists()

    def test_clear_file_preserves_other_fields(self, tmp_path):
        secret = self._secret(tmp_path)
        secret.file_path.parent.mkdir(parents=True)
        secret.file_path.write_text(json.dumps({"census_key": "k", "other": "v"}), encoding="utf-8")
        _clear_file(secret)
        data = json.loads(secret.file_path.read_text(encoding="utf-8"))
        assert data == {"other": "v"}


class FakeKeyring:
    """In-memory stand-in for the keyring module used in tests."""

    def __init__(self, fail=False):
        self.store = {}
        self.fail = fail

    def get_password(self, service, username):
        if self.fail:
            raise secret_store.KeyringError("no backend")
        return self.store.get((service, username))

    def set_password(self, service, username, value):
        if self.fail:
            raise secret_store.KeyringError("no backend")
        self.store[(service, username)] = value

    def delete_password(self, service, username):
        if self.fail or (service, username) not in self.store:
            raise secret_store.KeyringError("missing")
        del self.store[(service, username)]


class TestKeyringBackend:
    """Tests for the keyring-based credential read/write helpers."""

    def _secret(self):
        return get_secret("census")

    def test_available_false_when_module_none(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        assert secret_store.keyring_available() is False

    def test_available_true_when_module_present(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring())
        assert secret_store.keyring_available() is True

    def test_store_and_read_keyring(self, monkeypatch):
        fake = FakeKeyring()
        monkeypatch.setattr(secret_store, "keyring", fake)
        secret = self._secret()
        _store_keyring(secret, "kr-key")
        assert _read_keyring(secret) == "kr-key"

    def test_read_keyring_none_when_module_none(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        assert _read_keyring(self._secret()) is None

    def test_read_keyring_none_on_error(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring(fail=True))
        assert _read_keyring(self._secret()) is None

    def test_store_keyring_raises_on_error(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring(fail=True))
        with pytest.raises(secret_store.KeyringError):
            _store_keyring(self._secret(), "x")


class TestResolve:
    """Tests for secret_store.resolve priority order (env > keyring > file)."""

    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        monkeypatch.delenv("CENSUS_API_KEY", raising=False)

    def _secret(self, tmp_path):
        return Secret(
            name="census", keyring_service="svc", keyring_username="user",
            env_var="CENSUS_API_KEY",
            file_path=tmp_path / "creds.json", file_field="census_key",
        )

    def test_env_wins(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring())
        monkeypatch.setenv("CENSUS_API_KEY", "env-key")
        secret = self._secret(tmp_path)
        _store_keyring(secret, "kr-key")
        _write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "env-key"

    def test_keyring_beats_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring())
        secret = self._secret(tmp_path)
        _store_keyring(secret, "kr-key")
        _write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "kr-key"

    def test_file_when_no_env_or_keyring(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        _write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "file-key"

    def test_none_when_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        assert secret_store.resolve(self._secret(tmp_path)) is None

    def test_empty_env_falls_through(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        monkeypatch.setenv("CENSUS_API_KEY", "")
        secret = self._secret(tmp_path)
        _write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "file-key"


class TestStoreClearMask:
    """Tests for secret_store.store, clear, and mask public functions."""

    def _secret(self, tmp_path):
        return Secret(
            name="census", keyring_service="svc", keyring_username="user",
            env_var="CENSUS_API_KEY",
            file_path=tmp_path / "creds.json", file_field="census_key",
        )

    def test_store_writes_both_when_keyring_available(self, tmp_path, monkeypatch):
        fake = FakeKeyring()
        monkeypatch.setattr(secret_store, "keyring", fake)
        secret = self._secret(tmp_path)
        backends = secret_store.store(secret, "k")
        assert backends == ["keyring", "file"]
        assert _read_keyring(secret) == "k"
        assert _read_file(secret) == "k"

    def test_store_writes_file_only_without_keyring(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        assert secret_store.store(secret, "k") == ["file"]
        assert _read_file(secret) == "k"

    def test_store_writes_file_only_on_keyring_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring(fail=True))
        secret = self._secret(tmp_path)
        assert secret_store.store(secret, "k") == ["file"]
        assert _read_file(secret) == "k"

    def test_clear_removes_keyring_and_file(self, tmp_path, monkeypatch):
        fake = FakeKeyring()
        monkeypatch.setattr(secret_store, "keyring", fake)
        secret = self._secret(tmp_path)
        _store_keyring(secret, "k")
        _write_file(secret, "k")
        removed = secret_store.clear(secret)
        assert set(removed) == {"keyring", "file"}

    def test_clear_returns_empty_when_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        assert not secret_store.clear(self._secret(tmp_path))

    def test_clear_reports_only_file_when_not_in_keyring(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring())
        secret = self._secret(tmp_path)
        _write_file(secret, "k")
        assert secret_store.clear(secret) == ["file"]

    def test_mask_short_and_long(self):
        assert secret_store.mask("abcdef") == "****cdef"
        assert secret_store.mask("ab") == "****"


class TestRestoreFile:
    """Tests for restore_file()."""

    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        monkeypatch.delenv("CENSUS_API_KEY", raising=False)

    def _secret(self, tmp_path):
        return Secret(
            name="census", keyring_service="svc", keyring_username="user",
            env_var="CENSUS_API_KEY",
            file_path=tmp_path / "creds.json", file_field="census_key",
        )

    def test_restores_file_from_keyring(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring())
        secret = self._secret(tmp_path)
        _store_keyring(secret, "kr-key")
        assert not secret.file_path.exists()
        source = secret_store.restore_file(secret)
        assert source == "keyring"
        assert _read_file(secret) == "kr-key"

    def test_returns_none_when_nothing_available(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        assert secret_store.restore_file(secret) is None
        assert not secret.file_path.exists()

    def test_env_source_takes_precedence(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring())
        monkeypatch.setenv("CENSUS_API_KEY", "env-key")
        secret = self._secret(tmp_path)
        _store_keyring(secret, "kr-key")
        source = secret_store.restore_file(secret)
        assert source == "env"
        assert _read_file(secret) == "env-key"
