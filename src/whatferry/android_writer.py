"""Turn an iPhone -> Android conversion into a WhatsApp for Android backup.

The merged msgstore.db is encrypted the way WhatsApp's end-to-end encrypted
backup is (crypt15: AES-256-GCM under the 64-digit key, zlib inside), with
the original backup's header, so WhatsApp sees its own account and version.
A fresh random IV is drawn for every file: reusing the original's, as
wa-crypt-tools' own command line does by default, would put two different
plaintexts under one GCM nonce. The result is decrypted again and compared
byte for byte before it's handed back.

The output is a WhatsApp/ folder (Databases/msgstore.db.crypt15 and the
converted Media/), laid out as on the phone, ready to copy over.
"""

import hashlib
import json
import os
import shutil
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

from wa_crypt_tools.lib.db.db15 import Database15
from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory

from whatferry import android, workdir


class AndroidWriteError(Exception):
    """The backup can't be written; the message says why."""


@dataclass
class WriteReport:
    folder: str = ""
    backup: str = ""
    backup_bytes: int = 0
    media_files: int = 0
    verified: bool = False
    # False when the same-source guard was skipped on request.
    source_checked: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


def check_same_source(reference: Path, key, convert_run: Path) -> None:
    """Refuse an Android backup other than the one the conversion merged into."""
    try:
        made_from = json.loads((convert_run / "report.json").read_text())
    except (OSError, ValueError):
        raise AndroidWriteError(f"{convert_run} has no readable conversion report: convert again") from None
    if made_from.get("direction") != "iphone-to-android":
        raise AndroidWriteError(f"{convert_run} is an Android -> iPhone conversion")
    if not made_from.get("source_sha256"):
        raise AndroidWriteError("this conversion doesn't record which Android backup it was made from: convert again")
    plain, _ = android.decrypt(reference, key)
    if hashlib.sha256(plain).hexdigest() != made_from.get("source_sha256"):
        raise AndroidWriteError("this Android backup isn't the one the conversion was made from: check the newest "
                                "Android backup again and convert again")


def write_backup(reference: Path, key, convert_run: Path, target: Path | None = None,
                 check_source: bool = True) -> tuple[WriteReport, Path]:
    """Encrypt the converted msgstore.db like `reference`, and lay out the WhatsApp/ folder to copy to the phone."""
    merged = convert_run / "files" / "msgstore.db"
    if not merged.is_file():
        raise AndroidWriteError(f"{convert_run} has no converted msgstore.db")
    with reference.open("rb") as f:
        try:
            original = DatabaseFactory.from_file(f)
        except Exception as e:  # noqa: BLE001 - the library raises whatever its parser hits
            raise AndroidWriteError(f"{reference.name} is not a WhatsApp backup: {e}") from e
    if not isinstance(original, Database15):
        raise AndroidWriteError("only the end-to-end encrypted backup (msgstore.db.crypt15, with the 64-digit key) "
                                "can be written back")
    if check_source:  # off only on request
        check_same_source(reference, key, convert_run)

    run = workdir.new_run("android-backup")
    folder = target or run / "WhatsApp"
    if folder.exists():
        raise AndroidWriteError(f"{folder} already exists")
    (folder / "Databases").mkdir(parents=True, mode=0o700)
    plain = merged.read_bytes()
    encrypted = Database15(key=key).encrypt(key, original.props, zlib.compress(plain, 1))  # fresh IV
    out = folder / "Databases" / "msgstore.db.crypt15"
    workdir.write_private(out, encrypted)

    readback, _ = android.decrypt(out, key)
    if readback != plain:
        raise AndroidWriteError("the written backup doesn't decrypt to the converted database")

    media = convert_run / "files" / "Media"
    count = 0
    for path in sorted(p for p in media.rglob("*") if p.is_file()) if media.is_dir() else []:
        dest = folder / "Media" / path.relative_to(media)
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.link(path, dest)  # no extra space
        except OSError:
            shutil.copy2(path, dest)
        count += 1
    report = WriteReport(folder=str(folder), backup=str(out), backup_bytes=len(encrypted), media_files=count,
                         verified=True, source_checked=check_source)
    workdir.write_private(run / "write-report.json", json.dumps(report.as_dict(), indent=2).encode())
    return report, folder
