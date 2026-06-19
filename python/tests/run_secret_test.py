"""Tests for the `secret` command handlers in run.py."""

import pytest

import secret_store
from secret_store import _read_file, _write_file
import run


class TestSecretHandlers:
    """Tests for the secret_set, secret_get, and secret_clear command handlers."""

    def _secret(self, tmp_path):
        return secret_store.Secret(
            name="census", keyring_service="svc", keyring_username="user",
            env_var="CENSUS_API_KEY",
            file_path=tmp_path / "creds.json", file_field="census_key",
        )

    def test_set_stores_value(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        monkeypatch.setattr(run.getpass, "getpass", lambda prompt="": "typed-key")
        run.secret_set(secret)
        out = capsys.readouterr().out
        assert _read_file(secret) == "typed-key"
        assert "stored in" in out
        assert "Note:" in out

    def test_set_rejects_empty(self, tmp_path, monkeypatch):
        secret = self._secret(tmp_path)
        monkeypatch.setattr(run.getpass, "getpass", lambda prompt="": "   ")
        with pytest.raises(SystemExit):
            run.secret_set(secret)

    def test_get_masks_by_default(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        _write_file(secret, "abcdef")
        run.secret_get(secret, show=False)
        out = capsys.readouterr().out
        assert "****cdef" in out
        assert "abcdef" not in out

    def test_get_show_reveals(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        _write_file(secret, "abcdef")
        run.secret_get(secret, show=True)
        assert "abcdef" in capsys.readouterr().out

    def test_get_reports_not_set(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        run.secret_get(self._secret(tmp_path), show=False)
        assert "not set" in capsys.readouterr().out

    def test_clear_reports_removed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        _write_file(secret, "k")
        run.secret_clear(secret)
        assert "file" in capsys.readouterr().out
        assert _read_file(secret) is None

    def test_set_reports_both_backends(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "store", lambda secret, value: ["keyring", "file"])
        secret = self._secret(tmp_path)
        monkeypatch.setattr(run.getpass, "getpass", lambda prompt="": "typed-key")
        run.secret_set(secret)
        out = capsys.readouterr().out
        assert "OS keystore" in out
        assert str(secret.file_path) in out

    def test_handle_command_get_show_reveals(self, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        monkeypatch.setenv("CENSUS_API_KEY", "abcdef")
        run.handle_secret_command(["get", "census", "--show"])
        assert "abcdef" in capsys.readouterr().out

    def test_handle_command_restore_reports_each_secret(self, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "restore_file", lambda s: "keyring")
        run.handle_secret_command(["restore"])
        out = capsys.readouterr().out
        assert "census" in out
        assert "restored" in out

    def test_handle_command_restore_reports_nothing_to_restore(self, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "restore_file", lambda s: None)
        run.handle_secret_command(["restore"])
        assert "nothing to restore" in capsys.readouterr().out

    def test_set_without_name_errors(self):
        with pytest.raises(SystemExit):
            run.handle_secret_command(["set"])


class TestSecretInjection:
    """Tests for build_secret_env_and_flags injecting resolved secrets into Docker env."""

    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        monkeypatch.delenv("CENSUS_API_KEY", raising=False)

    def test_flags_and_env_when_resolvable(self, monkeypatch):
        monkeypatch.setattr(run.secret_store, "resolve", lambda secret: "resolved")
        env, flags = run.build_secret_env_and_flags()
        assert len(flags) == 2 * len(secret_store.SECRETS)
        for secret in secret_store.SECRETS.values():
            assert env[secret.env_var] == "resolved"
            assert secret.env_var in flags

    def test_no_flags_when_unset(self, monkeypatch):
        monkeypatch.setattr(run.secret_store, "resolve", lambda secret: None)
        env, flags = run.build_secret_env_and_flags()
        assert not flags
        assert "CENSUS_API_KEY" not in env
