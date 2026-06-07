"""Tests for the `secret` command handlers in run.py."""

import pytest

import secret_store
import run


class TestSecretHandlers:
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
        assert secret_store._read_file(secret) == "typed-key"
        assert "file" in capsys.readouterr().out

    def test_set_rejects_empty(self, tmp_path, monkeypatch):
        secret = self._secret(tmp_path)
        monkeypatch.setattr(run.getpass, "getpass", lambda prompt="": "   ")
        with pytest.raises(SystemExit):
            run.secret_set(secret)

    def test_get_masks_by_default(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        secret_store._write_file(secret, "abcdef")
        run.secret_get(secret, show=False)
        out = capsys.readouterr().out
        assert "****cdef" in out
        assert "abcdef" not in out

    def test_get_show_reveals(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        secret_store._write_file(secret, "abcdef")
        run.secret_get(secret, show=True)
        assert "abcdef" in capsys.readouterr().out

    def test_get_reports_not_set(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        run.secret_get(self._secret(tmp_path), show=False)
        assert "not set" in capsys.readouterr().out

    def test_clear_reports_removed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(secret_store, "keyring", None)
        secret = self._secret(tmp_path)
        secret_store._write_file(secret, "k")
        run.secret_clear(secret)
        assert "file" in capsys.readouterr().out


class TestSecretInjection:
    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        monkeypatch.delenv("CENSUS_API_KEY", raising=False)

    def test_flags_and_env_when_resolvable(self, monkeypatch):
        monkeypatch.setattr(run.secret_store, "resolve", lambda secret: "resolved")
        env, flags = run.build_secret_env_and_flags()
        assert env["CENSUS_API_KEY"] == "resolved"
        assert flags == ["-e", "CENSUS_API_KEY"]

    def test_no_flags_when_unset(self, monkeypatch):
        monkeypatch.setattr(run.secret_store, "resolve", lambda secret: None)
        env, flags = run.build_secret_env_and_flags()
        assert flags == []
        assert env.get("CENSUS_API_KEY") in (None, "")
