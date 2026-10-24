import hashlib
import plistlib
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    """Keep every run folder inside the test's own temporary directory."""
    home = tmp_path / "home"
    monkeypatch.setenv("WHATFERRY_HOME", str(home))
    return home


def make_sqlite(path: Path, script: str) -> Path:
    with closing(sqlite3.connect(path)) as db:
        db.executescript(script)
        db.commit()
    return path


def file_plist(size: int, mtime: int = 1_760_000_000) -> bytes:
    """A Manifest.db metadata plist, keyed-archived the way iOS writes it."""
    return plistlib.dumps({
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": plistlib.UID(1)},
        "$objects": ["$null", {
            "$class": plistlib.UID(2), "Size": size, "LastModified": mtime, "Birth": mtime,
            "ProtectionClass": 3, "Mode": 0o100644, "Flags": 0,
        }, {"$classname": "MBFile", "$classes": ["MBFile", "NSObject"]}],
    }, fmt=plistlib.FMT_BINARY)


class FakeBackup:
    """An unencrypted Finder backup folder, built file by file."""

    def __init__(self, folder: Path, device: str = "Test iPhone"):
        self.folder = folder
        folder.mkdir(parents=True)
        info = {"Device Name": device, "Product Type": "iPhone17,1", "Product Version": "26.1",
                "Last Backup Date": datetime(2026, 10, 24, 12, 0, 0)}
        (folder / "Info.plist").write_bytes(plistlib.dumps(info))
        (folder / "Manifest.plist").write_bytes(plistlib.dumps({"IsEncrypted": False, "Lockdown": {}}))
        with closing(sqlite3.connect(folder / "Manifest.db")) as db:
            db.execute("CREATE TABLE Files (fileID TEXT PRIMARY KEY, domain TEXT, relativePath TEXT, "
                       "flags INTEGER, file BLOB)")
            db.commit()

    def add(self, domain: str, path: str, data: bytes, mtime: int = 1_760_000_000) -> None:
        file_id = hashlib.sha1(f"{domain}-{path}".encode()).hexdigest()
        target = self.folder / file_id[:2] / file_id
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
        self._row(file_id, domain, path, 1, file_plist(len(data), mtime))

    def add_folder(self, domain: str, path: str) -> None:
        file_id = hashlib.sha1(f"{domain}-{path}".encode()).hexdigest()
        self._row(file_id, domain, path, 2, file_plist(0))

    def _row(self, *row) -> None:
        with closing(sqlite3.connect(self.folder / "Manifest.db")) as db:
            db.execute("INSERT OR REPLACE INTO Files VALUES (?, ?, ?, ?, ?)", row)
            db.commit()

    def copy(self, folder: Path) -> "FakeBackup":
        shutil.copytree(self.folder, folder)
        clone = FakeBackup.__new__(FakeBackup)
        clone.folder = folder
        return clone
