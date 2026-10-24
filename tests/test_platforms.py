"""What changes between macOS, Windows and Linux: folders, file names, URIs, bytes."""

import os
import sys
from pathlib import Path

import pytest

from conftest import FakeBackup, make_sqlite
from test_ios import SHARED, chat_storage
from whatferry import ios, sqlite_summary, workdir
from whatferry.cli import main
from whatferry.ios_backup import Backup, BackupError, backup_roots, find_backup, list_backups

# Characters that end or escape a path in a naive "file:" URI. Windows also
# forbids "?" in folder names, so it is only exercised elsewhere.
AWKWARD = "back up #1 100% done" if sys.platform == "win32" else "back up #1 100% done?"


def test_default_home_per_platform(monkeypatch):
    assert workdir.default_home("win32", {"LOCALAPPDATA": r"C:\Users\e\AppData\Local"}) == \
        Path(r"C:\Users\e\AppData\Local") / "whatferry"
    assert workdir.default_home("linux", {"XDG_DATA_HOME": "/data"}) == Path("/data/whatferry")
    assert workdir.default_home("linux", {}) == Path.home() / ".local" / "share" / "whatferry"
    assert workdir.default_home("darwin", {}) == Path.home() / ".local" / "share" / "whatferry"


def test_backup_roots_per_platform():
    assert backup_roots("darwin", {}) == [Path.home() / "Library/Application Support/MobileSync/Backup"]
    assert backup_roots("win32", {"USERPROFILE": "/u", "APPDATA": "/u/roam"}) == [
        Path("/u/Apple/MobileSync/Backup"), Path("/u/roam/Apple Computer/MobileSync/Backup")]
    assert backup_roots("linux", {}) == []


def test_backup_root_override_takes_several_folders():
    env = {"WHATFERRY_BACKUP_ROOT": os.pathsep.join(["/one", "", "/two"])}
    for platform in ("darwin", "win32", "linux"):
        assert backup_roots(platform, env) == [Path("/one"), Path("/two")]


def test_list_and_find_backups_across_roots(tmp_path):
    FakeBackup(tmp_path / "first" / "UDID-A")
    FakeBackup(tmp_path / "second" / "UDID-B", device="Other iPhone")
    roots = [tmp_path / "missing", tmp_path / "first", tmp_path / "second"]
    assert [(p.name, i.name) for p, i in list_backups(roots)] == [
        ("UDID-A", "Test iPhone"), ("UDID-B", "Other iPhone")]
    assert find_backup("UDID-B", roots) == tmp_path / "second" / "UDID-B"
    assert find_backup(str(tmp_path / "first" / "UDID-A"), roots) == tmp_path / "first" / "UDID-A"
    with pytest.raises(BackupError, match="no backup folder"):
        find_backup("UDID-C", roots)


def test_cli_lists_backups_from_the_override(tmp_path, monkeypatch, capsys):
    FakeBackup(tmp_path / "root" / "UDID-A")
    monkeypatch.setenv("WHATFERRY_BACKUP_ROOT", str(tmp_path / "root"))
    assert main(["ios", "backups"]) == 0
    assert "UDID-A  Test iPhone" in capsys.readouterr().out
    assert main(["ios", "inspect", "UDID-A"]) == 0


def test_cli_explains_how_to_back_up_when_none_found(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WHATFERRY_BACKUP_ROOT", str(tmp_path / "empty"))
    assert main(["ios", "backups"]) == 0
    assert "Encrypt local backup" in capsys.readouterr().out or sys.platform not in ("darwin", "win32")


def test_databases_open_from_folders_with_uri_characters(tmp_path):
    folder = tmp_path / AWKWARD
    folder.mkdir()
    db = make_sqlite(folder / "x.sqlite", "CREATE TABLE t (a); INSERT INTO t VALUES (1);")
    assert sqlite_summary.summarise(db).rows("t") == 1
    assert sqlite_summary.read_only_uri(db).startswith("file:///")


def test_backup_in_a_folder_with_uri_characters(tmp_path):
    fake = FakeBackup(tmp_path / AWKWARD / "UDID")
    data, _ = chat_storage(tmp_path / "ChatStorage.sqlite", messages=2)
    fake.add(SHARED, "ChatStorage.sqlite", data)
    report, _ = ios.inspect(Backup(fake.folder))
    assert report.chat_storages[0].counts["messages"] == 2


@pytest.mark.parametrize("given, expected", [
    ("Message/Media/a/b.jpg", "Message/Media/a/b.jpg"),
    ("Accounts/a:b/Chat?Storage*.sqlite", "Accounts/a_b/Chat_Storage_.sqlite"),
    ('x<y>"z|w', "x_y__z_w"),
    ("back\\slash", "back_slash"),
    ("../../etc/passwd", "etc/passwd"),
    ("./a//b/.", "a/b"),
    ("CON", "_CON"),
    ("nul.txt", "_nul.txt"),
    ("console.log", "console.log"),
    ("trailing. ", "trailing"),
    ("...", "_"),
    ("", "_"),
    ("tab\there", "tab_here"),
])
def test_safe_relative(given, expected):
    assert workdir.safe_relative(given) == Path(*expected.split("/"))


def test_extracted_names_are_safe_and_stay_inside_the_run(tmp_path):
    fake = FakeBackup(tmp_path / "UDID")
    data, _ = chat_storage(tmp_path / "ChatStorage.sqlite", messages=1)
    fake.add(SHARED, "Accounts/a:b/ChatStorage.sqlite", data)
    fake.add(SHARED, "../../escape.sqlite", data)
    report, run = ios.inspect(Backup(fake.folder))
    extracted = sorted(Path(d.extracted_to) for d in report.databases)
    assert extracted == sorted([run / "files" / SHARED / "Accounts" / "a_b" / "ChatStorage.sqlite",
                                run / "files" / SHARED / "escape.sqlite"])
    assert all(p.resolve().is_relative_to(run.resolve()) for p in extracted)
    # Reports keep the iPhone's own path, unrewritten.
    assert sorted(d.path for d in report.databases) == ["../../escape.sqlite", "Accounts/a:b/ChatStorage.sqlite"]


def test_private_writes_keep_bytes_exact(tmp_path):
    data = bytes(range(256)) * 4 + b"\n\r\n\x1a"
    workdir.write_private(tmp_path / "f", data)
    assert (tmp_path / "f").read_bytes() == data


def test_private_writes_refuse_to_replace(tmp_path):
    workdir.write_private(tmp_path / "f", b"first")
    with pytest.raises(FileExistsError):
        workdir.write_private(tmp_path / "f", b"second")
    assert (tmp_path / "f").read_bytes() == b"first"
