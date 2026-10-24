"""Read an iPhone backup, encrypted or not.

Finder (macOS), iTunes or the Apple Devices app (Windows) and idevicebackup2
(Linux, or anywhere) all write the same format: a backup folder holds
Manifest.plist (device info, and the keybag when
encrypted), Manifest.db (one row per file: domain, relative path, flags and a
metadata plist) and the files themselves, stored as <id[:2]>/<id>. Nothing
here writes to a backup folder.
"""

import os
import plistlib
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from iphone_backup_decrypt import EncryptedBackup
from iphone_backup_decrypt.exceptions import IncorrectPassphraseError
from iphone_backup_decrypt.utils import FilePlist

from whatferry import workdir
from whatferry.sqlite_summary import read_only_uri

# Every WhatsApp container: the app, its shared group, extensions, and the
# Business app (net.whatsapp.WhatsAppSMB).
WHATSAPP_DOMAINS = "%net.whatsapp.%"

FILE, FOLDER, SYMLINK = 1, 2, 4


class BackupError(Exception):
    pass


class WrongPassphrase(BackupError):
    pass


@dataclass(frozen=True)
class Entry:
    file_id: str
    domain: str
    path: str
    flags: int
    size: int
    mtime: int | None
    bplist: bytes

    @property
    def key(self) -> tuple[str, str]:
        return self.domain, self.path


@dataclass
class DeviceInfo:
    name: str | None
    model: str | None
    ios_version: str | None
    backup_date: str | None
    encrypted: bool


def device_info(folder: Path) -> DeviceInfo:
    info = _plist(folder / "Info.plist")
    manifest = _plist(folder / "Manifest.plist")
    lockdown = manifest.get("Lockdown", {})
    date = info.get("Last Backup Date") or manifest.get("Date")
    return DeviceInfo(
        name=info.get("Device Name") or lockdown.get("DeviceName"),
        model=info.get("Product Type") or lockdown.get("ProductType"),
        ios_version=info.get("Product Version") or lockdown.get("ProductVersion"),
        backup_date=date.isoformat(timespec="seconds") if isinstance(date, datetime) else None,
        encrypted=bool(manifest.get("IsEncrypted")),
    )


def _plist(path: Path) -> dict:
    try:
        with path.open("rb") as f:
            return plistlib.load(f)
    except FileNotFoundError:
        return {}


HOW_TO_BACK_UP = {
    "darwin": "In Finder: select the iPhone, tick 'Encrypt local backup', then 'Back Up Now'.",
    "win32": "In the Apple Devices app (or iTunes): select the iPhone, tick 'Encrypt local backup', "
             "then 'Back Up Now'.",
}
HOW_TO_BACK_UP_ELSEWHERE = (
    "With libimobiledevice: `idevicebackup2 encryption on` once, then `idevicebackup2 backup --full <folder>`; "
    "set WHATFERRY_BACKUP_ROOT to that folder.")


def how_to_back_up(platform: str = sys.platform) -> str:
    return HOW_TO_BACK_UP.get(platform, HOW_TO_BACK_UP_ELSEWHERE)


# What a later diff needs from a backup: the file list and, when encrypted,
# the keybag that unlocks it. The files themselves are not copied.
SNAPSHOT_FILES = ("Manifest.db", "Manifest.plist", "Info.plist")


def snapshot_manifest(folder: Path, dest: Path) -> Path:
    """Keep a backup's index, so it can be compared after the next backup.

    Finder, iTunes and idevicebackup2 update the same folder in place, so the
    "before" state is gone once the "after" backup is made. The index is a few
    MB where the whole backup can be tens of GB.
    """
    dest.mkdir(parents=True, mode=0o700)
    for name in SNAPSHOT_FILES:
        if (folder / name).exists():
            workdir.write_private(dest / name, (folder / name).read_bytes())
    return dest


def backup_roots(platform: str = sys.platform, env=os.environ) -> list[Path]:
    """The folders that hold one sub-folder per backup, most likely first.

    WHATFERRY_BACKUP_ROOT (several joined with the platform's path separator)
    replaces the defaults; Linux has none, since idevicebackup2 writes
    wherever it is told.
    """
    if env.get("WHATFERRY_BACKUP_ROOT"):
        return [Path(p).expanduser() for p in env["WHATFERRY_BACKUP_ROOT"].split(os.pathsep) if p]
    if platform == "darwin":
        return [Path.home() / "Library" / "Application Support" / "MobileSync" / "Backup"]
    if platform == "win32":
        profile = Path(env.get("USERPROFILE") or Path.home())
        appdata = Path(env.get("APPDATA") or profile / "AppData" / "Roaming")
        # The Apple Devices app and Microsoft Store iTunes use the first,
        # iTunes from apple.com the second.
        return [profile / "Apple" / "MobileSync" / "Backup",
                appdata / "Apple Computer" / "MobileSync" / "Backup"]
    return []


def list_backups(roots: list[Path] | None = None) -> list[tuple[Path, DeviceInfo]]:
    found = []
    for root in backup_roots() if roots is None else roots:
        try:
            folders = sorted(p for p in root.iterdir() if (p / "Manifest.db").exists())
        except PermissionError:
            if sys.platform == "darwin":
                raise BackupError(
                    f"macOS refused to list {root}. Give your terminal Full Disk Access "
                    "(System Settings → Privacy & Security → Full Disk Access) and try again.") from None
            raise BackupError(f"permission denied listing {root}") from None
        except (FileNotFoundError, NotADirectoryError):
            continue
        found += [(p, device_info(p)) for p in folders]
    return found


def find_backup(name: str, roots: list[Path] | None = None) -> Path:
    """A backup folder from a path, or from the folder name a listing shows."""
    folder = Path(name).expanduser()
    if folder.is_dir():
        return folder
    for root in backup_roots() if roots is None else roots:
        if (root / name).is_dir():
            return root / name
    raise BackupError(f"no backup folder {name!r}: give its full path, or see `whatferry ios backups`")


class Backup:
    """One backup folder, read through its manifest."""

    def __init__(self, folder: Path, passphrase: str | None = None):
        if not (folder / "Manifest.db").exists():
            raise BackupError(f"{folder} is not a backup folder (no Manifest.db)")
        self.folder = folder
        self.info = device_info(folder)
        self.passphrase = passphrase if self.info.encrypted else None
        self._encrypted: EncryptedBackup | None = None
        if self.info.encrypted:
            if passphrase is None:
                raise BackupError("this backup is encrypted: a passphrase is needed")
            self._encrypted = EncryptedBackup(backup_directory=str(folder), passphrase=passphrase)
            try:
                self._encrypted.test_decryption()
            except IncorrectPassphraseError:
                raise WrongPassphrase("the backup passphrase is wrong") from None

    def entries(self, domain_like: str = WHATSAPP_DOMAINS) -> list[Entry]:
        query = ("SELECT fileID, domain, relativePath, flags, file FROM Files "
                 "WHERE domain LIKE ? ORDER BY domain, relativePath")
        if self._encrypted:
            with self._encrypted.manifest_db_cursor() as cur:
                rows = cur.execute(query, (domain_like,)).fetchall()
        else:
            with closing(sqlite3.connect(read_only_uri(self.folder / "Manifest.db"), uri=True)) as db:
                rows = db.execute(query, (domain_like,)).fetchall()
        entries = []
        for file_id, domain, path, flags, bplist in rows:
            meta = FilePlist(bplist)
            entries.append(Entry(file_id, domain, path, flags, meta.filesize, meta.mtime, bplist))
        return entries

    def read(self, entry: Entry) -> bytes:
        if entry.flags != FILE:
            raise BackupError(f"{entry.domain}/{entry.path} is not a file")
        if self._encrypted:
            if entry.size == 0:
                return b""
            # By file ID, not by path: a path lookup goes through SQL LIKE.
            return self._encrypted._decrypt_inner_file(file_id=entry.file_id, file_bplist=entry.bplist)
        return (self.folder / entry.file_id[:2] / entry.file_id).read_bytes()
