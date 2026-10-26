"""Build encrypted iPhone backups the way iOS does, for tests.

A keybag (TLV) holds one key per protection class, each wrapped (RFC 3394)
with a key derived from the passphrase (PBKDF2-SHA256, then PBKDF2-SHA1).
Manifest.plist keeps the keybag and the manifest key, wrapped with class 4.
Manifest.db and every file are AES-256-CBC (zero IV, PKCS#7) under their
own keys; a file's key sits wrapped in its MBFile entry.
"""

import hashlib
import os
import plistlib
import sqlite3
import struct
from contextlib import closing
from datetime import datetime
from pathlib import Path

from Crypto.Cipher import AES

CLASSES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)


def _tlv(tag: bytes, value) -> bytes:
    if isinstance(value, int):
        value = struct.pack(">L", value)
    return tag + struct.pack(">L", len(value)) + value


def _pad(data: bytes) -> bytes:
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def _encrypt(data: bytes, key: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv=b"\0" * 16).encrypt(_pad(data))


def _mbfile(path: str, size: int, protection: int, mode: int, wrapped: bytes | None) -> bytes:
    objects: list = ["$null"]
    root = {"$class": None, "RelativePath": plistlib.UID(2), "LastModified": 1760000000, "LastStatusChange": 1760000000,
            "Birth": 1760000000, "Size": size, "InodeNumber": 42, "Mode": mode, "UserID": 501, "GroupID": 501,
            "Flags": 0, "ProtectionClass": protection}
    objects += [root, path]
    if wrapped is not None:
        objects.append({"NS.data": wrapped, "$class": plistlib.UID(4)})
        objects.append({"$classname": "NSMutableData", "$classes": ["NSMutableData", "NSData", "NSObject"]})
        root["EncryptionKey"] = plistlib.UID(3)
    objects.append({"$classname": "MBFile", "$classes": ["MBFile", "NSObject"]})
    root["$class"] = plistlib.UID(len(objects) - 1)
    return plistlib.dumps({"$version": 100000, "$archiver": "NSKeyedArchiver", "$top": {"root": plistlib.UID(1)},
                           "$objects": objects}, fmt=plistlib.FMT_BINARY)


def make_encrypted_backup(folder: Path, passphrase: str, files: dict[tuple[str, str], bytes],
                          folders: list[tuple[str, str]] = ()) -> Path:
    folder.mkdir(parents=True)
    salt, dpsl = os.urandom(20), os.urandom(20)
    round1 = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), dpsl, 10, 32)
    passphrase_key = hashlib.pbkdf2_hmac("sha1", round1, salt, 10, 32)
    class_keys = {c: os.urandom(32) for c in CLASSES}
    keybag = (_tlv(b"VERS", 3) + _tlv(b"TYPE", 1) + _tlv(b"UUID", os.urandom(16)) + _tlv(b"HMCK", os.urandom(40))
              + _tlv(b"WRAP", 0) + _tlv(b"SALT", salt) + _tlv(b"ITER", 10) + _tlv(b"DPWT", 1)
              + _tlv(b"DPIC", 10) + _tlv(b"DPSL", dpsl))
    for c, key in class_keys.items():
        keybag += (_tlv(b"UUID", os.urandom(16)) + _tlv(b"CLAS", c) + _tlv(b"WRAP", 2) + _tlv(b"KTYP", 0)
                   + _tlv(b"WPKY", AES.new(passphrase_key, AES.MODE_KW).seal(key)))
    manifest_key = os.urandom(32)
    (folder / "Manifest.plist").write_bytes(plistlib.dumps({
        "BackupKeyBag": keybag, "IsEncrypted": True, "Lockdown": {},
        "ManifestKey": struct.pack("<l", 4) + AES.new(class_keys[4], AES.MODE_KW).seal(manifest_key),
    }))
    (folder / "Info.plist").write_bytes(plistlib.dumps({
        "Device Name": "Test iPhone", "Product Type": "iPhone17,1", "Product Version": "27.0",
        "Last Backup Date": datetime(2026, 10, 25, 10, 0, 0)}))
    index = folder / "index.tmp"
    with closing(sqlite3.connect(index)) as db:
        db.execute("CREATE TABLE Files (fileID TEXT PRIMARY KEY, domain TEXT, relativePath TEXT, flags INTEGER, file BLOB)")
        db.execute("CREATE TABLE Properties (key TEXT PRIMARY KEY, value BLOB)")
        for domain, path in folders:
            fid = hashlib.sha1(f"{domain}-{path}".encode()).hexdigest()
            db.execute("INSERT INTO Files VALUES (?, ?, ?, 2, ?)", (fid, domain, path, _mbfile(path, 0, 0, 0o40755, None)))
        for (domain, path), data in files.items():
            fid = hashlib.sha1(f"{domain}-{path}".encode()).hexdigest()
            key = os.urandom(32)
            wrapped = struct.pack("<l", 3) + AES.new(class_keys[3], AES.MODE_KW).seal(key)
            (folder / fid[:2]).mkdir(exist_ok=True)
            (folder / fid[:2] / fid).write_bytes(_encrypt(data, key))
            db.execute("INSERT INTO Files VALUES (?, ?, ?, 1, ?)", (fid, domain, path, _mbfile(path, len(data), 3, 0o100644, wrapped)))
        db.commit()
    (folder / "Manifest.db").write_bytes(_encrypt(index.read_bytes(), manifest_key))
    index.unlink()
    return folder
