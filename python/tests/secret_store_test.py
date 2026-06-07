"""Tests for secret_store.py."""

import json

import pytest

import secret_store
from secret_store import SECRETS, Secret, get_secret


class TestRegistry:
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
        secret_store._write_file(secret, "file-key")
        assert secret_store._read_file(secret) == "file-key"

    def test_read_missing_file_returns_none(self, tmp_path):
        assert secret_store._read_file(self._secret(tmp_path)) is None

    def test_read_malformed_file_returns_none(self, tmp_path):
        secret = self._secret(tmp_path)
        secret.file_path.parent.mkdir(parents=True)
        secret.file_path.write_text("not json{{{")
        assert secret_store._read_file(secret) is None

    def test_clear_file_removes_field_and_empty_file(self, tmp_path):
        secret = self._secret(tmp_path)
        secret_store._write_file(secret, "file-key")
        removed = secret_store._clear_file(secret)
        assert removed is True
        assert not secret.file_path.exists()

    def test_clear_file_preserves_other_fields(self, tmp_path):
        secret = self._secret(tmp_path)
        secret.file_path.parent.mkdir(parents=True)
        secret.file_path.write_text(json.dumps({"census_key": "k", "other": "v"}))
        secret_store._clear_file(secret)
        data = json.loads(secret.file_path.read_text())
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
        secret_store._store_keyring(secret, "kr-key")
        assert secret_store._read_keyring(secret) == "kr-key"

    def test_read_keyring_none_when_module_none(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        assert secret_store._read_keyring(self._secret()) is None

    def test_read_keyring_none_on_error(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring(fail=True))
        assert secret_store._read_keyring(self._secret()) is None

    def test_store_keyring_raises_on_error(self, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring(fail=True))
        with pytest.raises(secret_store.KeyringError):
            secret_store._store_keyring(self._secret(), "x")


class TestResolve:
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
        secret_store._store_keyring(secret, "kr-key")
        secret_store._write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "env-key"

    def test_keyring_beats_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring())
        secret = self._secret(tmp_path)
        secret_store._store_keyring(secret, "kr-key")
        secret_store._write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "kr-key"

    def test_file_when_no_env_or_keyring(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        secret_store._write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "file-key"

    def test_none_when_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        assert secret_store.resolve(self._secret(tmp_path)) is None

    def test_empty_env_falls_through(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        monkeypatch.setenv("CENSUS_API_KEY", "")
        secret = self._secret(tmp_path)
        secret_store._write_file(secret, "file-key")
        assert secret_store.resolve(secret) == "file-key"


class TestStoreClearMask:
    def _secret(self, tmp_path):
        return Secret(
            name="census", keyring_service="svc", keyring_username="user",
            env_var="CENSUS_API_KEY",
            file_path=tmp_path / "creds.json", file_field="census_key",
        )

    def test_store_uses_keyring_when_available(self, tmp_path, monkeypatch):
        fake = FakeKeyring()
        monkeypatch.setattr(secret_store, "keyring", fake)
        secret = self._secret(tmp_path)
        where = secret_store.store(secret, "k")
        assert where == "keyring"
        assert not secret.file_path.exists()
        assert secret_store._read_keyring(secret) == "k"

    def test_store_falls_back_to_file_when_no_keyring(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        assert secret_store.store(secret, "k") == "file"
        assert secret_store._read_file(secret) == "k"

    def test_store_falls_back_to_file_on_backend_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", FakeKeyring(fail=True))
        secret = self._secret(tmp_path)
        assert secret_store.store(secret, "k") == "file"
        assert secret_store._read_file(secret) == "k"

    def test_clear_removes_keyring_and_file(self, tmp_path, monkeypatch):
        fake = FakeKeyring()
        monkeypatch.setattr(secret_store, "keyring", fake)
        secret = self._secret(tmp_path)
        secret_store._store_keyring(secret, "k")
        secret_store._write_file(secret, "k")
        removed = secret_store.clear(secret)
        assert set(removed) == {"keyring", "file"}

    def test_clear_returns_empty_when_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(secret_store, "keyring", None)
        assert secret_store.clear(self._secret(tmp_path)) == []

    def test_mask_short_and_long(self):
        assert secret_store.mask("abcdef") == "****cdef"
        assert secret_store.mask("ab") == "****"
