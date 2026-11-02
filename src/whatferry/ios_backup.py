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
import re
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from iphone_backup_decrypt import EncryptedBackup, iphone_backup, utils
from iphone_backup_decrypt.exceptions import IncorrectPassphraseError
from iphone_backup_decrypt.utils import FilePlist

from whatferry import workdir
from whatferry.sqlite_summary import read_only_uri


class _PrivateTempfile:
    """The library decrypts Manifest.db, the list of every file on the phone,
    into tempfile.mkdtemp(): the system's shared temporary folder, where it
    stays if the process dies. Its only use of tempfile; sent to whatferry's
    private folder instead."""

    @staticmethod
    def mkdtemp() -> str:
        return tempfile.mkdtemp(prefix="manifest-", dir=workdir.private_temp())


iphone_backup.tempfile = _PrivateTempfile

FILE_ID = re.compile(r"[0-9a-f]{40}")

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
    """A plist's contents; empty when it is missing or damaged (a backup Finder was still writing)."""
    try:
        with path.open("rb") as f:
            data = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def decrypt_file(reader: EncryptedBackup, folder: Path, file_id: str, bplist: bytes) -> bytes:
    """One file of an encrypted backup, through an unlocked reader.

    As the library's own _decrypt_inner_file does, without its INFO line on
    stdout: iOS's recorded size is often off for live SQLite files.
    """
    meta = FilePlist(bplist)
    key = reader.keybag.unwrap_key_for_class(meta.protection_class, meta.encryption_key)
    data = Path(utils.backup_file_path(str(folder), file_id)).read_bytes()
    return utils.remove_cbc_padding(utils.aes_decrypt_cbc(data=data, key=key))


HOW_TO_BACK_UP = "Connect the iPhone with a cable, unlock it, and run `whatferry ios backup`."
BY_HAND = {
    "darwin": "Or in Finder: select the iPhone, tick 'Encrypt local backup', then 'Back Up Now'.",
    "win32": "Or in the Apple Devices app (or iTunes): select the iPhone, tick 'Encrypt local backup', "
             "then 'Back Up Now'.",
}
BY_HAND_ELSEWHERE = (
    "Or with libimobiledevice: `idevicebackup2 encryption on` once, then `idevicebackup2 backup --full <folder>`; "
    "set WHATFERRY_BACKUP_ROOT to that folder.")


def how_to_back_up(platform: str = sys.platform) -> str:
    return f"{HOW_TO_BACK_UP} {BY_HAND.get(platform, BY_HAND_ELSEWHERE)}"


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

    whatferry's own (<home>/backups, where `whatferry ios backup` writes)
    comes first, then the one Finder, iTunes or the Apple Devices app uses.
    WHATFERRY_BACKUP_ROOT (several joined with the platform's path separator)
    replaces them all.
    """
    if env.get("WHATFERRY_BACKUP_ROOT"):
        return [Path(p).expanduser() for p in env["WHATFERRY_BACKUP_ROOT"].split(os.pathsep) if p]
    own = [workdir.home(platform, env) / "backups"]
    if platform == "darwin":
        return own + [Path.home() / "Library" / "Application Support" / "MobileSync" / "Backup"]
    if platform == "win32":
        profile = Path(env.get("USERPROFILE") or Path.home())
        appdata = Path(env.get("APPDATA") or profile / "AppData" / "Roaming")
        # The Apple Devices app and Microsoft Store iTunes use the first,
        # iTunes from apple.com the second.
        return own + [profile / "Apple" / "MobileSync" / "Backup",
                      appdata / "Apple Computer" / "MobileSync" / "Backup"]
    return own


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
            try:
                self._encrypted = EncryptedBackup(backup_directory=str(folder), passphrase=passphrase)
                self._encrypted.test_decryption()
            except IncorrectPassphraseError:
                raise WrongPassphrase("the backup passphrase is wrong") from None
            except Exception as e:  # noqa: BLE001 - a damaged keybag or index: the library's own types
                raise BackupError(f"can't open the backup in {folder}: {e!r}") from e

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
            return decrypt_file(self._encrypted, self.folder, entry.file_id, entry.bplist)
        if not FILE_ID.fullmatch(entry.file_id):
            raise BackupError(f"{entry.domain}/{entry.path} has a malformed file ID in Manifest.db")
        return (self.folder / entry.file_id[:2] / entry.file_id).read_bytes()
