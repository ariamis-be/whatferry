import dataclasses
import hashlib
import plistlib
import shutil
import sqlite3
import stat
import sys
from contextlib import closing
from pathlib import Path

import pytest

from conftest import FakeBackup, make_sqlite
from encrypted_backup import make_encrypted_backup
from whatferry import ios
from whatferry.cli import main
from whatferry.ios_backup import Backup, BackupError, list_backups

SHARED = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"
APP = "AppDomain-net.whatsapp.WhatsApp"

CHAT_STORAGE_SCHEMA = """
    CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER PRIMARY KEY, Z_NAME VARCHAR, Z_SUPER INTEGER, Z_MAX INTEGER);
    CREATE TABLE ZWACHATSESSION (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, ZCONTACTJID VARCHAR, ZPARTNERNAME VARCHAR);
    CREATE TABLE ZWAMESSAGE (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, ZCHATSESSION INTEGER,
                             ZMESSAGEDATE TIMESTAMP, ZTEXT VARCHAR);
    CREATE TABLE ZWAMEDIAITEM (Z_PK INTEGER PRIMARY KEY, ZMESSAGE INTEGER, ZMEDIALOCALPATH VARCHAR);
"""


def chat_storage(path, messages: int, wal_messages: int = 0):
    """A ChatStorage.sqlite whose last `wal_messages` rows live only in its -wal file.

    Returns the database bytes and the -wal bytes, copied while the writer is
    still open, the way an iPhone backup catches a running WhatsApp.
    """
    with closing(sqlite3.connect(path)) as db:
        db.executescript(CHAT_STORAGE_SCHEMA)
        db.execute("INSERT INTO Z_PRIMARYKEY VALUES (1, 'WAChatSession', 0, 1), (2, 'WAMessage', 0, ?)",
                   (messages + wal_messages,))
        db.execute("INSERT INTO ZWACHATSESSION VALUES (1, 1, '32470000001@s.whatsapp.net', 'Alice')")
        db.executemany("INSERT INTO ZWAMESSAGE VALUES (?, 2, 1, ?, 'secret text')",
                       [(n, 800_000_000 + n) for n in range(1, messages + 1)])
        db.commit()
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA wal_autocheckpoint = 0")
        db.executemany("INSERT INTO ZWAMESSAGE VALUES (?, 2, 1, ?, 'newer text')",
                       [(n, 900_000_000 + n) for n in range(messages + 1, messages + wal_messages + 1)])
        db.commit()
        main_bytes = path.read_bytes()
        wal = path.with_name(path.name + "-wal")
        wal_bytes = wal.read_bytes() if wal.exists() else b""
    return main_bytes, wal_bytes


@pytest.fixture
def backup(tmp_path):
    fake = FakeBackup(tmp_path / "00008140-AAAA")
    db, wal = chat_storage(tmp_path / "ChatStorage.sqlite", messages=3, wal_messages=2)
    assert wal and b"newer text" not in db, "the fixture must leave its newest rows in the WAL"
    fake.add_folder(SHARED, "Message")
    fake.add(SHARED, "ChatStorage.sqlite", db)
    fake.add(SHARED, "ChatStorage.sqlite-wal", wal)
    fake.add(SHARED, "Message/Media/32470000001@s.whatsapp.net/a/b/IMG.jpg", b"\xff\xd8 jpeg")
    fake.add(SHARED, "Message/Media/32470000001@s.whatsapp.net/a/b/not-a.db", b"not sqlite at all")
    contacts = make_sqlite(tmp_path / "ContactsV2.sqlite", "CREATE TABLE ZWAADDRESSBOOKCONTACT (Z_PK INTEGER);")
    fake.add(SHARED, "ContactsV2.sqlite", contacts.read_bytes())
    fake.add(APP, "Library/Preferences/net.whatsapp.WhatsApp.plist", b"bplist00")
    fake.add("HomeDomain", "Library/SMS/sms.db", b"unrelated")
    return fake


def test_finds_whatsapp_domains_and_skips_others(backup):
    report, _ = ios.inspect(Backup(backup.folder))
    assert set(report.domains) == {APP, SHARED}
    assert report.domains[SHARED]["files"] == 5
    assert report.top_folders[SHARED]["Message"] == 2
    assert report.device.name == "Test iPhone"
    assert report.device.encrypted is False


def test_chat_storage_includes_rows_only_in_the_wal(backup):
    report, run = ios.inspect(Backup(backup.folder))
    [store] = report.chat_storages
    assert store.counts["messages"] == 5
    assert store.counts["chats"] == 1
    assert store.counts["media"] == 0
    assert store.counts["group members"] is None
    assert store.core_data_entities == {"WAChatSession": 1, "WAMessage": 5}
    assert store.first_message == "2026-05-09T06:13:21+00:00"
    assert store.last_message == "2029-07-09T16:00:05+00:00"
    assert "CREATE TABLE ZWAMESSAGE" in (run / "files" / SHARED / "ChatStorage.sqlite.schema.sql").read_text()


def test_every_database_is_described_and_non_sqlite_db_files_skipped(backup):
    report, _ = ios.inspect(Backup(backup.folder))
    assert sorted(d.path for d in report.databases) == ["ChatStorage.sqlite", "ContactsV2.sqlite"]


def test_backup_folder_is_left_untouched(backup):
    before = {p: p.read_bytes() for p in backup.folder.rglob("*") if p.is_file()}
    ios.inspect(Backup(backup.folder))
    after = {p: p.read_bytes() for p in backup.folder.rglob("*") if p.is_file()}
    assert before == after


def test_two_accounts_show_as_two_chat_storages(backup, tmp_path):
    db, _ = chat_storage(tmp_path / "second.sqlite", messages=7)
    backup.add(SHARED, "Accounts/2/ChatStorage.sqlite", db)
    report, _ = ios.inspect(Backup(backup.folder))
    assert sorted(s.counts["messages"] for s in report.chat_storages) == [5, 7]


def test_diff_names_what_adding_an_account_touched(backup, tmp_path):
    after = backup.copy(tmp_path / "after")
    db, _ = chat_storage(tmp_path / "second.sqlite", messages=1)
    after.add(SHARED, "Accounts/2/ChatStorage.sqlite", db)
    after.add(APP, "Library/Preferences/net.whatsapp.WhatsApp.plist", b"bplist00 changed", mtime=1_770_000_000)
    after.add("HomeDomain", "Library/SMS/sms.db", b"changed too, but not WhatsApp", mtime=1_770_000_000)

    result = ios.diff(Backup(backup.folder), Backup(after.folder))
    assert [e.path for e in result.added] == ["Accounts/2/ChatStorage.sqlite"]
    assert result.removed == []
    assert [b.path for _, b in result.changed] == ["Library/Preferences/net.whatsapp.WhatsApp.plist"]
    assert result.by_folder()[f"{SHARED}  Accounts/"] == {"added": 1}


def test_cli_inspect_prints_shape_not_contents(backup, capsys):
    assert main(["ios", "inspect", str(backup.folder)]) == 0
    out = capsys.readouterr().out
    assert "NOT encrypted" in out
    assert "ChatStorage.sqlite" in out
    for secret in ("secret text", "newer text", "Alice"):
        assert secret not in out


def test_cli_diff_writes_full_list(backup, tmp_path, capsys, private_home):
    after = backup.copy(tmp_path / "after")
    after.add(SHARED, "Accounts/2/marker", b"x")
    assert main(["ios", "diff", str(backup.folder), str(after.folder)]) == 0
    assert "1 added" in capsys.readouterr().out
    [diff_file] = private_home.glob("*-ios-diff/diff.txt")
    assert f"+ {SHARED}/Accounts/2/marker" in diff_file.read_text()


def test_not_a_backup_folder(tmp_path):
    with pytest.raises(BackupError, match="not a backup folder"):
        Backup(tmp_path)


def test_file_ids_match_the_ios_scheme(backup):
    entry = next(e for e in Backup(backup.folder).entries() if e.path == "ChatStorage.sqlite")
    assert entry.file_id == hashlib.sha1(f"{SHARED}-ChatStorage.sqlite".encode()).hexdigest()
    shutil.rmtree(backup.folder / entry.file_id[:2])
    with pytest.raises(FileNotFoundError):
        Backup(backup.folder).read(entry)


def test_databases_differing_only_in_case_are_both_kept(backup, tmp_path):
    other = make_sqlite(tmp_path / "other.sqlite", "CREATE TABLE t (x); INSERT INTO t VALUES (1);")
    backup.add(SHARED, "Stats.sqlite", other.read_bytes())
    backup.add(SHARED, "stats.sqlite", other.read_bytes())
    report, _ = ios.inspect(Backup(backup.folder))
    assert {d.path for d in report.databases} >= {"Stats.sqlite", "stats.sqlite"}


def test_a_malformed_file_id_is_never_followed(backup):
    entry = next(e for e in Backup(backup.folder).entries() if e.path == "ChatStorage.sqlite")
    with pytest.raises(BackupError, match="malformed file ID"):
        Backup(backup.folder).read(dataclasses.replace(entry, file_id="../../../etc/passwd"))


def test_one_damaged_backup_doesnt_hide_the_others(backup, tmp_path):
    damaged = backup.copy(tmp_path / "00008140-BBBB")
    (damaged.folder / "Info.plist").write_bytes(b"bplist00 cut short")
    listed = {folder.name: info for folder, info in list_backups([tmp_path])}
    assert listed["00008140-AAAA"].name == "Test iPhone" and listed["00008140-BBBB"].name is None


def test_an_encrypted_backups_index_is_decrypted_privately(tmp_path, private_home):
    folder = make_encrypted_backup(tmp_path / "00008140-CCCC", "pw", {(SHARED, "x"): b"x"})
    backup = Backup(folder, "pw")
    temporary = Path(backup._encrypted._temporary_folder)
    assert temporary.parent == private_home / "tmp"
    if sys.platform != "win32":  # Windows has no Unix modes; the profile's ACL protects it
        assert stat.S_IMODE(temporary.parent.stat().st_mode) == 0o700


def test_a_damaged_keybag_is_a_backup_error(tmp_path):
    folder = make_encrypted_backup(tmp_path / "00008140-DDDD", "pw", {(SHARED, "x"): b"x"})
    manifest = plistlib.loads((folder / "Manifest.plist").read_bytes())
    del manifest["BackupKeyBag"]
    (folder / "Manifest.plist").write_bytes(plistlib.dumps(manifest))
    with pytest.raises(BackupError, match="can't open the backup"):
        Backup(folder, "pw")
