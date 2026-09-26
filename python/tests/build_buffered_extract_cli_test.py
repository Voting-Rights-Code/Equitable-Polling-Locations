"""Tests for build_buffered_extract_cli script."""

import pytest

from python.scripts.build_buffered_extract_cli import main


def test_cli_builds_and_prints_path(monkeypatch, capsys):
    monkeypatch.setattr(
        'python.scripts.build_buffered_extract_cli.build_buffered_pbf',
        lambda slug: f'/data/{slug}-buffered.osm.pbf',
    )
    assert main(['georgia']) == 0
    assert '/data/georgia-buffered.osm.pbf' in capsys.readouterr().out


def test_cli_rejects_unknown_slug():
    with pytest.raises(SystemExit) as exc:
        main(['atlantis'])
    assert exc.value.code == 2
