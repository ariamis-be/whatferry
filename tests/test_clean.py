"""`whatferry clean`: what it deletes from whatferry's folder, and what it leaves."""

import io
import os
import sys

import pytest

from whatferry import workdir
from whatferry.cli import main


@pytest.fixture
def filled(private_home):
    """whatferry's folder after a transfer, plus things clean must not touch."""
    for n, kind in enumerate(("android", "ios", "convert", "backup", "backup-2", "ios-diff")):
        run = private_home / f"20261025-12000{n}-{kind}"
        run.mkdir(parents=True)
        (run / "report.json").write_bytes(b"x" * 100)
    (private_home / "snapshots" / "20261025-120003-ios").mkdir(parents=True)
    (private_home / "tmp").mkdir()
    (private_home / "state.json").write_text("{}")
    (private_home / "settings.json").write_text('{"theme": "dark"}')
    (private_home / "backups" / "UDID").mkdir(parents=True)
    (private_home / "notes.txt").write_text("mine")
    (private_home / "2026-not-a-run").mkdir()
    return private_home


def _left(home):
    return sorted(p.name for p in home.iterdir())


def test_leftovers_are_runs_snapshots_tmp_and_progress(filled):
    names = [p.name for p in workdir.leftovers(filled)]
    assert names[:6] == sorted(names[:6]) and all(n.startswith("20261025-") for n in names[:6])
    assert names[6:] == ["snapshots", "tmp", "state.json"]
    assert [p.name for p in workdir.leftovers(filled, backups=True)][-1] == "backups"


def test_no_folder_yet(private_home, capsys):
    assert workdir.leftovers(private_home) == []
    assert main(["clean", "--yes"]) == 0
    assert "Nothing to delete" in capsys.readouterr().out


def test_dry_run_deletes_nothing(filled, capsys):
    before = _left(filled)
    assert main(["clean", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "9 to delete" in out and "--backups deletes them too" in out
    assert _left(filled) == before


def test_yes_keeps_settings_backups_and_unknown_files(filled, capsys):
    assert main(["clean", "--yes"]) == 0
    assert "Deleted 9" in capsys.readouterr().out
    assert _left(filled) == ["2026-not-a-run", "backups", "notes.txt", "settings.json"]


def test_backups_only_when_asked(filled):
    assert main(["clean", "--yes", "--backups"]) == 0
    assert _left(filled) == ["2026-not-a-run", "notes.txt", "settings.json"]


def test_asks_first(filled, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert main(["clean"]) == 1
    assert "Nothing deleted" in capsys.readouterr().out
    assert "state.json" in _left(filled)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert main(["clean"]) == 0
    assert "state.json" not in _left(filled)


def test_without_a_terminal_it_needs_yes(filled, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    before = _left(filled)
    assert main(["clean"]) == 1
    assert "add --yes" in capsys.readouterr().err
    assert _left(filled) == before


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need extra rights on Windows")
def test_links_are_removed_not_followed(private_home, tmp_path):
    outside = tmp_path / "outside"
    (outside / "keep").mkdir(parents=True)
    private_home.mkdir()
    os.symlink(outside, private_home / "tmp")
    os.symlink(outside, private_home / "20261025-120000-ios")
    assert [p.name for p in workdir.leftovers(private_home)] == ["tmp"]
    assert workdir.freed([private_home / "tmp"])[0] < 1000
    assert main(["clean", "--yes"]) == 0
    assert (outside / "keep").is_dir()
    assert _left(private_home) == ["20261025-120000-ios"]


def test_hard_links_count_once_and_only_when_all_go(private_home, tmp_path):
    media = tmp_path / "android-media" / "photo.jpg"
    media.parent.mkdir()
    media.write_bytes(b"p" * 5000)
    first, second = private_home / "20261025-120000-convert", private_home / "20261025-120001-convert"
    for run in (first, second):
        run.mkdir(parents=True)
        os.link(media, run / "photo.jpg")
    (first / "own.jpg").write_bytes(b"o" * 3000)
    os.link(first / "own.jpg", second / "own.jpg")
    # photo.jpg keeps a link outside, so deleting both frees only own.jpg, once.
    assert sum(workdir.freed([first, second])) < 3000 + 1000
    assert sum(workdir.freed([first, second])) >= 3000
    assert sum(workdir.freed([first])) < 1000
    media.unlink()
    assert sum(workdir.freed([first, second])) >= 8000
