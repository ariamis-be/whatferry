"""Writing into a copy of an iPhone backup, read back by an independent reader."""

import hashlib
import json
import plistlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from iphone_backup_decrypt import EncryptedBackup

from conftest import FakeBackup
from encrypted_backup import make_encrypted_backup
from test_convert import ACCOUNT, ANDROID, IOS
from conftest import make_sqlite
from whatferry import backup_writer, convert, ios
from whatferry.backup_writer import BackupWriter, WriteError, file_id, write_conversion
from whatferry.cli import main
from whatferry.ios_backup import Backup, WrongPassphrase

SHARED = backup_writer.SHARED_DOMAIN
PASS = "correct horse"


def snapshot(folder: Path) -> dict[str, bytes]:
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def read(folder: Path, domain: str, path: str, passphrase: str = PASS) -> bytes:
    return EncryptedBackup(backup_directory=str(folder), passphrase=passphrase).extract_file_as_bytes(path, domain_like=domain)


@pytest.fixture
def backup(tmp_path):
    return make_encrypted_backup(tmp_path / "backups" / "00008160-0001", PASS, {
        (SHARED, "ChatStorage.sqlite"): b"main account database",
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): b"second account database",
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite-wal"): b"a write-ahead log",
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite-shm"): b"shared memory",
        (SHARED, "Message/Media/a.jpg"): b"\xff\xd8 an old photo",
    }, folders=[(SHARED, "Message"), (SHARED, "Message/Media"), (SHARED, "data"), (SHARED, ACCOUNT)])


def test_fixture_is_readable_by_the_independent_reader(backup):
    assert read(backup, SHARED, "Message/Media/a.jpg") == b"\xff\xd8 an old photo"


def test_replace_remove_add_and_read_back(backup, tmp_path):
    original = snapshot(backup)
    new_db = tmp_path / "new.sqlite"
    new_db.write_bytes(b"merged database " * 1000)
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\xff\xd8 a new photo")
    out = tmp_path / "out" / backup.name
    with BackupWriter(backup, out, PASS) as w:
        w.replace(SHARED, f"{ACCOUNT}/ChatStorage.sqlite", new_db)
        assert w.remove(SHARED, f"{ACCOUNT}/ChatStorage.sqlite-wal")
        assert not w.remove(SHARED, f"{ACCOUNT}/nothing-here")
        w.add(SHARED, f"{ACCOUNT}/Message/Media/1@s.whatsapp.net/a/b/P.jpg", photo)
        report = w.commit()

    assert snapshot(backup) == original, "the source backup must not change"
    assert read(out, SHARED, f"{ACCOUNT}/ChatStorage.sqlite") == new_db.read_bytes()
    assert read(out, SHARED, f"{ACCOUNT}/Message/Media/1@s.whatsapp.net/a/b/P.jpg") == photo.read_bytes()
    assert read(out, SHARED, "ChatStorage.sqlite") == b"main account database"  # untouched files still read
    assert (report.verified_files, report.added_files, report.added_folders) == (2, 1, 5)

    entries = {(e.domain, e.path): e for e in Backup(out, PASS).entries()}
    assert (SHARED, f"{ACCOUNT}/ChatStorage.sqlite-wal") not in entries
    assert not (out / file_id(SHARED, f"{ACCOUNT}/ChatStorage.sqlite-wal")[:2] /
                file_id(SHARED, f"{ACCOUNT}/ChatStorage.sqlite-wal")).exists()
    for folder in ("Message", "Message/Media", "Message/Media/1@s.whatsapp.net", "Message/Media/1@s.whatsapp.net/a",
                   "Message/Media/1@s.whatsapp.net/a/b"):
        assert entries[(SHARED, f"{ACCOUNT}/{folder}")].flags == 2, folder
    added = entries[(SHARED, f"{ACCOUNT}/Message/Media/1@s.whatsapp.net/a/b/P.jpg")]
    assert added.file_id == hashlib.sha1(f"{SHARED}-{ACCOUNT}/Message/Media/1@s.whatsapp.net/a/b/P.jpg".encode()).hexdigest()
    assert added.size == len(b"\xff\xd8 a new photo")
    root = plistlib.loads(added.bplist)
    root = root["$objects"][root["$top"]["root"].data]
    assert root["ProtectionClass"] == 3 and root["Mode"] == 0o100644


def test_new_keys_are_fresh_and_per_file(backup, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"same bytes")
    b.write_bytes(b"same bytes")
    out = tmp_path / "out" / backup.name
    with BackupWriter(backup, out, PASS) as w:
        w.add(SHARED, "x/a", a)
        w.add(SHARED, "x/b", b)
        w.commit()
    blob = lambda p: (out / file_id(SHARED, p)[:2] / file_id(SHARED, p)).read_bytes()
    assert blob("x/a") != blob("x/b"), "the same bytes must encrypt differently under different keys"


def test_wrong_passphrase(backup, tmp_path):
    with pytest.raises(WrongPassphrase):
        BackupWriter(backup, tmp_path / "out" / backup.name, "nope")


def test_target_must_not_exist(backup, tmp_path):
    (tmp_path / "out" / backup.name).mkdir(parents=True)
    with pytest.raises(WriteError, match="already exists"):
        BackupWriter(backup, tmp_path / "out" / backup.name, PASS)


def test_adding_an_existing_path_or_replacing_a_missing_one_is_refused(backup, tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"x")
    with BackupWriter(backup, tmp_path / "out" / backup.name, PASS) as w:
        with pytest.raises(WriteError, match="already exists"):
            w.add(SHARED, "ChatStorage.sqlite", f)
        with pytest.raises(WriteError, match="is not a file"):
            w.replace(SHARED, "no/such.sqlite", f)


def test_unencrypted_backups_too(tmp_path):
    fake = FakeBackup(tmp_path / "plain")
    fake.add_folder(SHARED, "Message")
    fake.add(SHARED, "ChatStorage.sqlite", b"old")
    new = tmp_path / "new"
    new.write_bytes(b"new")
    out = tmp_path / "out" / "plain"
    with BackupWriter(fake.folder, out) as w:
        w.replace(SHARED, "ChatStorage.sqlite", new)
        w.add(SHARED, "Message/Media/x.jpg", new)
        report = w.commit()
    assert report.verified_files == 2 and not report.encrypted
    entry = next(e for e in Backup(out).entries() if e.path == "ChatStorage.sqlite")
    assert Backup(out).read(entry) == b"new"


def test_a_conversion_end_to_end(tmp_path, monkeypatch):
    """Android history, converted, written into the backup it came from, inspected again."""
    android = make_sqlite(tmp_path / "msgstore.db", ANDROID)
    second = make_sqlite(tmp_path / "second.sqlite", IOS)
    media = tmp_path / "media" / "WhatsApp Images" / "Sent"
    media.mkdir(parents=True)
    (media / "IMG-1.jpg").write_bytes(b"\xff\xd8 a jpeg")
    source = make_encrypted_backup(tmp_path / "backups" / "00008160-0002", PASS, {
        (SHARED, "ChatStorage.sqlite"): make_sqlite(tmp_path / "main.sqlite", IOS).read_bytes(),
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): second.read_bytes(),
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite-wal"): b"stale log",
    }, folders=[(SHARED, "data"), (SHARED, ACCOUNT)])

    report, run = convert.convert(android, second, tmp_path / "media", ACCOUNT)
    written, target = write_conversion(source, PASS, run, ACCOUNT)
    assert written.verified_files == 1 + report.media_files_copied
    assert written.removed == [f"{SHARED}/{ACCOUNT}/ChatStorage.sqlite-wal"]

    inspected, _ = ios.inspect(Backup(target, PASS))
    store = next(d for d in inspected.databases if d.path == f"{ACCOUNT}/ChatStorage.sqlite")
    assert store.counts["messages"] == report.checks["messages"]
    assert any(p.endswith(".jpg") for p in (e.path for e in Backup(target, PASS).entries()))


def test_cli_writes_a_conversion(tmp_path, monkeypatch, capsys):
    android = make_sqlite(tmp_path / "msgstore.db", ANDROID)
    second = make_sqlite(tmp_path / "second.sqlite", IOS)
    source = make_encrypted_backup(tmp_path / "backups" / "00008160-0003", PASS, {
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): second.read_bytes()}, folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    _, run = convert.convert(android, second, None, ACCOUNT)
    monkeypatch.setenv("WHATFERRY_BACKUP_PASSPHRASE", PASS)
    assert main(["ios", "write", str(source), str(run), "--account-folder", ACCOUNT]) == 0
    out = capsys.readouterr().out
    assert "read back and verified" in out and source.name in out


# The guard: a conversion only goes into the backup it was made from.

def account_backup(tmp_path, name, change=0):
    """An encrypted backup holding the second account; `change` makes its database differ."""
    second = make_sqlite(tmp_path / f"{name}.sqlite", IOS)
    with closing(sqlite3.connect(second)) as db:
        db.execute(f"PRAGMA user_version = {change}")
        db.commit()
    return make_encrypted_backup(tmp_path / "backups" / name, PASS, {
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): second.read_bytes()}, folders=[(SHARED, "data"), (SHARED, ACCOUNT)])


def converted_from(source, tmp_path):
    """Check the backup, then convert into the database the check extracted: the wizard's flow."""
    android = make_sqlite(tmp_path / f"msgstore-{source.name}.db", ANDROID)
    _, run = ios.inspect(Backup(source, PASS))
    return convert.convert(android, run / "files" / SHARED / ACCOUNT / "ChatStorage.sqlite", None, ACCOUNT)[1]


def test_guard_lets_the_checked_backup_through(tmp_path):
    source = account_backup(tmp_path, "00008160-0010")
    written, _ = write_conversion(source, PASS, converted_from(source, tmp_path), ACCOUNT)
    assert written.verified_files == 1


def test_guard_refuses_a_newer_backup(tmp_path):
    """Converted from one backup, written into a later one where the account had moved on."""
    run = converted_from(account_backup(tmp_path, "00008160-0011"), tmp_path)
    newer = account_backup(tmp_path, "00008160-0012", change=1)
    with pytest.raises(WriteError, match="isn't the one the conversion was made"):
        write_conversion(newer, PASS, run, ACCOUNT)


def test_guard_refuses_the_wrong_account(tmp_path):
    source = account_backup(tmp_path, "00008160-0013")
    with pytest.raises(WriteError, match=f"made for {ACCOUNT}, not the main account"):
        write_conversion(source, PASS, converted_from(source, tmp_path), None)


def test_guard_refuses_a_conversion_without_a_record(tmp_path):
    source = account_backup(tmp_path, "00008160-0014")
    run = converted_from(source, tmp_path)
    report = json.loads((run / "report.json").read_text())
    del report["source_sha256"]
    (run / "report.json").unlink()
    (run / "report.json").write_text(json.dumps(report))
    with pytest.raises(WriteError, match="convert again"):
        write_conversion(source, PASS, run, ACCOUNT)
    (run / "report.json").unlink()
    with pytest.raises(WriteError, match="no conversion report"):
        write_conversion(source, PASS, run, ACCOUNT)


def test_guard_can_be_skipped_on_request(tmp_path, monkeypatch, capsys):
    run = converted_from(account_backup(tmp_path, "00008160-0015"), tmp_path)
    newer = account_backup(tmp_path, "00008160-0016", change=1)
    written, _ = write_conversion(newer, PASS, run, ACCOUNT, check_source=False)
    assert written.verified_files == 1 and not written.source_checked

    monkeypatch.setenv("WHATFERRY_BACKUP_PASSPHRASE", PASS)
    args = ["ios", "write", str(newer), str(run), "--account-folder", ACCOUNT, "--to", str(tmp_path / "w")]
    assert main(args) == 1, "refused without the flag"
    capsys.readouterr()
    assert main([*args, "--skip-source-check"]) == 0
    assert "Source check skipped" in capsys.readouterr().out


def test_manifest_stays_a_valid_encrypted_index(backup, tmp_path):
    out = tmp_path / "out" / backup.name
    with BackupWriter(backup, out, PASS) as w:
        w.commit()
    with EncryptedBackup(backup_directory=str(out), passphrase=PASS).manifest_db_cursor() as cur:
        assert cur.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with closing(sqlite3.connect(out / "Manifest.db")) as db, pytest.raises(sqlite3.DatabaseError):
        db.execute("SELECT * FROM Files").fetchall()  # still encrypted on disk
