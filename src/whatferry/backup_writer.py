"""Write changed and added files into a copy of an iPhone backup.

The original backup is never touched: it is copied first (an APFS clone on
macOS, so instant and free until files change), and every write goes to the
copy. Encrypted backups are written the way iOS writes them:

- each file is AES-256-CBC with a zero IV and PKCS#7 padding, under its own
  random key;
- that key is wrapped (RFC 3394) with the keybag key of the file's
  protection class and stored in the file's MBFile entry in Manifest.db, as
  4 bytes of class (little-endian) + the 40-byte wrapped key;
- Manifest.db itself is encrypted the same way under the manifest key, which
  Manifest.plist keeps wrapped and which stays the same.

New entries are cloned from entries iOS wrote in the same backup (a file
from the same domain, a folder from the same domain) with only the path,
size, times, inode and key changed. After writing, the copy is read back
with an independent reader and every written file compared.
"""

import copy
import hashlib
import json
import plistlib
import secrets
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path

from Crypto.Cipher import AES
from iphone_backup_decrypt import EncryptedBackup
from iphone_backup_decrypt.exceptions import IncorrectPassphraseError

from whatferry import workdir
from whatferry.ios_backup import FILE, FOLDER, BackupError, WrongPassphrase, device_info

BLOCK = 16
CHUNK = 1 << 20


class WriteError(Exception):
    pass


def file_id(domain: str, path: str) -> str:
    return hashlib.sha1(f"{domain}-{path}".encode()).hexdigest()


def pad(data: bytes) -> bytes:
    n = BLOCK - len(data) % BLOCK
    return data + bytes([n]) * n


def unpad(data: bytes) -> bytes:
    n = data[-1]
    if not 1 <= n <= BLOCK or data[-n:] != bytes([n]) * n:
        raise WriteError("bad padding: wrong key or damaged file")
    return data[:-n]


def encrypt(data: bytes, key: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv=b"\0" * BLOCK).encrypt(pad(data))


def decrypt(data: bytes, key: bytes) -> bytes:
    return unpad(AES.new(key, AES.MODE_CBC, iv=b"\0" * BLOCK).decrypt(data))


def wrap(kek: bytes, key: bytes) -> bytes:
    return AES.new(kek, AES.MODE_KW).seal(key)


def clone_folder(source: Path, target: Path) -> None:
    """Copy a backup folder; on macOS an APFS clone, so no space or time is spent."""
    if target.exists():
        raise WriteError(f"{target} already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        if subprocess.run(["cp", "-cR", str(source), str(target)], capture_output=True).returncode == 0:
            return
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target)


@dataclass
class WriteReport:
    folder: str = ""
    encrypted: bool = False
    replaced: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    added_files: int = 0
    added_folders: int = 0
    added_bytes: int = 0
    verified_files: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


class BackupWriter:
    """Changes to a copy of a backup. Use as a context manager; commit() writes the index."""

    def __init__(self, source: Path, target: Path, passphrase: str | None = None):
        if not (source / "Manifest.db").exists():
            raise BackupError(f"{source} is not a backup folder (no Manifest.db)")
        clone_folder(source, target)
        self.folder = target
        self.passphrase = passphrase
        self.encrypted = device_info(target).encrypted
        self.report = WriteReport(folder=str(target), encrypted=self.encrypted)
        self._work = workdir.new_run("backup-index")
        self._index = self._work / "Manifest.db"
        if self.encrypted:
            if passphrase is None:
                raise BackupError("this backup is encrypted: a passphrase is needed")
            reader = EncryptedBackup(backup_directory=str(target), passphrase=passphrase)
            try:
                reader._read_and_unlock_keybag()
            except IncorrectPassphraseError:
                raise WrongPassphrase("the backup passphrase is wrong") from None
            self.class_keys = dict(reader.keybag.classes_keys)
            wrapped = reader._manifest_plist["ManifestKey"]
            self.manifest_key = reader.keybag.unwrap_key_for_class(struct.unpack("<l", wrapped[:4])[0], wrapped[4:])
            workdir.write_private(self._index, decrypt((target / "Manifest.db").read_bytes(), self.manifest_key))
        else:
            workdir.write_private(self._index, (target / "Manifest.db").read_bytes())
        self.db = sqlite3.connect(self._index)
        self._written: dict[str, Path] = {}  # fileID -> the plain file it must decrypt to

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.db.close()
        shutil.rmtree(self._work, ignore_errors=True)
        return False

    # Entries

    def _entry(self, domain: str, path: str):
        return self.db.execute("SELECT fileID, flags, file FROM Files WHERE domain = ? AND relativePath = ?",
                               (domain, path)).fetchone()

    def _template(self, domain: str, flags: int) -> dict:
        row = self.db.execute("SELECT file FROM Files WHERE domain = ? AND flags = ? AND length(file) > 0 LIMIT 1",
                              (domain, flags)).fetchone()
        if row is None:
            row = self.db.execute("SELECT file FROM Files WHERE flags = ? AND length(file) > 0 LIMIT 1", (flags,)).fetchone()
        if row is None:
            raise WriteError(f"no {'file' if flags == FILE else 'folder'} entry to copy the format from")
        return plistlib.loads(row[0])

    @staticmethod
    def _root(plist: dict) -> dict:
        return plist["$objects"][plist["$top"]["root"].data]

    def _set_path(self, plist: dict, path: str) -> None:
        root = self._root(plist)
        if "RelativePath" in root:
            plist["$objects"][root["RelativePath"].data] = path
        else:
            plist["$objects"].append(path)
            root["RelativePath"] = plistlib.UID(len(plist["$objects"]) - 1)

    def _set_key(self, plist: dict, data_size: int) -> bytes | None:
        """Give an entry a fresh file key; returns the key (None when unencrypted)."""
        root = self._root(plist)
        root["Size"] = data_size
        now = int(time.time())
        root["LastModified"] = root["LastStatusChange"] = now
        if not self.encrypted:
            root.pop("EncryptionKey", None)
            return None
        protection = root.get("ProtectionClass", 3)
        class_key = self.class_keys.get(protection)
        if class_key is None:
            raise WriteError(f"the keybag has no key for protection class {protection}")
        key = secrets.token_bytes(32)
        blob = struct.pack("<l", protection) + wrap(class_key, key)
        objects = plist["$objects"]
        if "EncryptionKey" in root:
            objects[root["EncryptionKey"].data]["NS.data"] = blob
        else:
            data_class = len(objects)
            objects.append({"$classname": "NSMutableData", "$classes": ["NSMutableData", "NSData", "NSObject"]})
            objects.append({"NS.data": blob, "$class": plistlib.UID(data_class)})
            root["EncryptionKey"] = plistlib.UID(len(objects) - 1)
        return key

    def _write_data(self, fid: str, source: Path, key: bytes | None) -> int:
        target = self.folder / fid[:2] / fid
        target.parent.mkdir(exist_ok=True)
        data = source.read_bytes()
        target.unlink(missing_ok=True)  # never write through into a clone's shared blocks
        target.write_bytes(encrypt(data, key) if key else data)
        self._written[fid] = source
        return len(data)

    def replace(self, domain: str, path: str, source: Path) -> None:
        row = self._entry(domain, path)
        if row is None or row[1] != FILE:
            raise WriteError(f"{domain}/{path} is not a file in this backup")
        fid, _, blob = row
        plist = plistlib.loads(blob)
        key = self._set_key(plist, source.stat().st_size)
        self._write_data(fid, source, key)
        self.db.execute("UPDATE Files SET file = ? WHERE fileID = ?", (plistlib.dumps(plist, fmt=plistlib.FMT_BINARY), fid))
        self.report.replaced.append(f"{domain}/{path}")

    def remove(self, domain: str, path: str) -> bool:
        row = self._entry(domain, path)
        if row is None:
            return False
        (self.folder / row[0][:2] / row[0]).unlink(missing_ok=True)
        self.db.execute("DELETE FROM Files WHERE fileID = ?", (row[0],))
        self.report.removed.append(f"{domain}/{path}")
        return True

    def _folder(self, domain: str, path: str) -> None:
        if not path or self._entry(domain, path):
            return
        self._folder(domain, path.rsplit("/", 1)[0] if "/" in path else "")
        plist = copy.deepcopy(self._template(domain, FOLDER))
        root = self._root(plist)
        self._set_path(plist, path)
        root.pop("EncryptionKey", None)
        now = int(time.time())
        root.update(Size=0, LastModified=now, LastStatusChange=now, Birth=now, InodeNumber=secrets.randbits(40))
        self.db.execute("INSERT INTO Files (fileID, domain, relativePath, flags, file) VALUES (?, ?, ?, ?, ?)",
                        (file_id(domain, path), domain, path, FOLDER, plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)))
        self.report.added_folders += 1

    def add(self, domain: str, path: str, source: Path) -> None:
        if self._entry(domain, path):
            raise WriteError(f"{domain}/{path} already exists in this backup")
        self._folder(domain, path.rsplit("/", 1)[0] if "/" in path else "")
        plist = copy.deepcopy(self._template(domain, FILE))
        root = self._root(plist)
        self._set_path(plist, path)
        root.pop("ExtendedAttributes", None)
        root.update(Birth=int(time.time()), InodeNumber=secrets.randbits(40), Mode=0o100644)
        key = self._set_key(plist, source.stat().st_size)
        fid = file_id(domain, path)
        size = self._write_data(fid, source, key)
        self.db.execute("INSERT INTO Files (fileID, domain, relativePath, flags, file) VALUES (?, ?, ?, ?, ?)",
                        (fid, domain, path, FILE, plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)))
        self.report.added_files += 1
        self.report.added_bytes += size

    # Finishing

    def commit(self) -> WriteReport:
        self.db.commit()
        self.db.execute("PRAGMA journal_mode = DELETE")
        self.db.close()
        index = self._index.read_bytes()
        (self.folder / "Manifest.db").unlink()
        (self.folder / "Manifest.db").write_bytes(encrypt(index, self.manifest_key) if self.encrypted else index)
        self.db = sqlite3.connect(self._index)
        self.verify()
        return self.report

    def verify(self) -> None:
        """Read every written file back through an independent reader and compare."""
        if self.encrypted:
            reader = EncryptedBackup(backup_directory=str(self.folder), passphrase=self.passphrase)
            with reader.manifest_db_cursor() as cur:
                rows = {fid: blob for fid, blob in cur.execute("SELECT fileID, file FROM Files")}
            for fid, source in self._written.items():
                if fid not in rows:
                    raise WriteError(f"{fid} missing from the written index")
                data = reader._decrypt_inner_file(file_id=fid, file_bplist=rows[fid])
                if data != source.read_bytes():
                    raise WriteError(f"{fid} doesn't read back as written")
                self.report.verified_files += 1
        else:
            with closing(sqlite3.connect(f"file:{self.folder / 'Manifest.db'}?mode=ro", uri=True)) as db:
                ids = {r[0] for r in db.execute("SELECT fileID FROM Files")}
            for fid, source in self._written.items():
                if fid not in ids or (self.folder / fid[:2] / fid).read_bytes() != source.read_bytes():
                    raise WriteError(f"{fid} doesn't read back as written")
                self.report.verified_files += 1


SHARED_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"


def write_conversion(source: Path, passphrase: str | None, convert_run: Path, account_folder: str | None,
                     target: Path | None = None) -> tuple[WriteReport, Path]:
    """Put a `whatferry convert` result into a copy of the backup it was made from."""
    files = convert_run / "files"
    merged = files / "ChatStorage.sqlite"
    if not merged.is_file():
        raise WriteError(f"{convert_run} has no converted ChatStorage.sqlite")
    prefix = f"{account_folder}/" if account_folder else ""
    run = workdir.new_run("backup")
    target = target or run / source.name
    with BackupWriter(source, target, passphrase) as writer:
        writer.replace(SHARED_DOMAIN, f"{prefix}ChatStorage.sqlite", merged)
        # The merged database is whole: an old write-ahead log left beside it
        # would be replayed over it on the phone.
        for suffix in ("-wal", "-shm"):
            writer.remove(SHARED_DOMAIN, f"{prefix}ChatStorage.sqlite{suffix}")
        media = files / (account_folder or "") / "Message" / "Media"
        for path in sorted(p for p in media.rglob("*") if p.is_file()) if media.is_dir() else []:
            writer.add(SHARED_DOMAIN, f"{prefix}Message/Media/{path.relative_to(media).as_posix()}", path)
        report = writer.commit()
    workdir.write_private(run / "write-report.json", json.dumps(report.as_dict(), indent=2).encode())
    return report, target


