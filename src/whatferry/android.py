"""Read an Android WhatsApp backup: decrypt msgstore.db.crypt15 and describe it.

The backup must come from WhatsApp's end-to-end encrypted backup with the
64-digit key option, so the key is known without root. A Java key file
pulled from a rooted phone (/data/data/com.whatsapp/files/key) works too.
"""

import logging
import re
import zlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
from wa_crypt_tools.lib.key.keyfactory import KeyFactory

from whatferry import sqlite_summary, workdir

# wa-crypt-tools logs freely, including a "your phone number ends with" line;
# whatferry reports what it needs itself.
logging.getLogger("wa_crypt_tools").setLevel(logging.CRITICAL)


class DecryptError(Exception):
    pass


@dataclass
class BackupHeader:
    app_version: str | None
    number_ends_with: str | None


def parse_key(text: str):
    """A Key15 from the 64-digit key, ignoring the spaces it is shown with."""
    digits = re.sub(r"\s+", "", text).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digits):
        raise DecryptError("the key must be 64 hexadecimal characters (spaces are ignored)")
    return KeyFactory.from_hex(digits)


def load_key(path: Path):
    """A key from a file holding the 64-digit key, or a Java key file."""
    raw = path.read_bytes()
    try:
        return parse_key(raw.decode("ascii"))
    except (UnicodeDecodeError, DecryptError):
        key = KeyFactory.from_file(path)
        if key is None:
            raise DecryptError(f"{path} is neither a 64-digit key nor a WhatsApp key file") from None
        return key


def decrypt(encrypted: Path, key) -> tuple[bytes, BackupHeader]:
    """The plain SQLite bytes of a crypt14 or crypt15 backup."""
    with encrypted.open("rb") as f:
        try:
            db = DatabaseFactory.from_file(f)
        except Exception as e:
            raise DecryptError(f"{encrypted.name} is not a WhatsApp crypt14/15 backup: {e}") from e
        payload = db.decrypt(key, f.read())
    # The factory keeps the parsed header's info (BackupExpiry) in db.props;
    # crypt12 backups have none.
    props = getattr(db, "props", None)
    info = props.get_proto() if props else None
    header = BackupHeader(
        app_version=(info.app_version or None) if info else None,
        number_ends_with=(info.jidSuffix or None) if info else None,
    )
    # A wrong key still "decrypts", into noise: only a clean zlib stream
    # holding a SQLite file proves the key matched.
    inflater = zlib.decompressobj()
    try:
        plain = inflater.decompress(payload)
    except zlib.error:
        raise DecryptError("decryption failed: the key does not match this backup") from None
    if not inflater.eof:
        raise DecryptError("the backup is truncated (damaged or still being written)")
    if not sqlite_summary.is_sqlite(plain):
        raise DecryptError("decrypted data is not a SQLite database")
    return plain, header


@dataclass
class Report:
    source: str
    header: BackupHeader | None
    user_version: int
    layout: str
    counts: dict[str, int | None] = field(default_factory=dict)
    jid_servers: dict[str, int] = field(default_factory=dict)
    message_types: dict[int, int] = field(default_factory=dict)
    first_message: str | None = None
    last_message: str | None = None
    tables: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


# Tables the conversion will have to carry over, by what they hold.
COUNTED = {
    "chats": "chat",
    "messages": "message",
    "media": "message_media",
    "quoted replies": "message_quoted",
    "reactions and other add-ons": "message_add_on",
    "contact cards": "message_vcard",
    "locations": "message_location",
    "calls": "call_log",
    "contacts and groups (jid)": "jid",
}


def describe(db_path: Path, *, source: str, header: BackupHeader | None) -> Report:
    summary = sqlite_summary.summarise(db_path)
    if summary.table("message"):
        layout = "modern (message, chat, jid tables)"
    elif summary.table("messages"):
        layout = "legacy (single messages table): too old for whatferry, update WhatsApp and back up again"
    else:
        layout = "unrecognised: no message or messages table"
    report = Report(source=source, header=header, user_version=summary.user_version,
                    layout=layout, tables=len(summary.tables))
    report.counts = {label: summary.rows(table) for label, table in COUNTED.items()}
    with sqlite_summary.open_read_only(db_path) as db:
        if summary.table("jid"):
            report.jid_servers = dict(db.execute(
                "SELECT coalesce(server, '?'), count(*) FROM jid GROUP BY 1 ORDER BY 2 DESC"))
        if summary.table("message"):
            report.message_types = dict(db.execute(
                "SELECT message_type, count(*) FROM message GROUP BY 1 ORDER BY 2 DESC"))
            first, last = db.execute(
                "SELECT min(timestamp), max(timestamp) FROM message WHERE timestamp > 0").fetchone()
            report.first_message = _iso_from_millis(first)
            report.last_message = _iso_from_millis(last)
    return report


def _iso_from_millis(ms: int | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="seconds") if ms else None


def inspect(backup: Path, key) -> tuple[Report, Path]:
    """Decrypt (or copy) the backup into a new run folder and describe it."""
    run = workdir.new_run("android")
    db_path = run / "msgstore.db"
    header = None
    if key is None:
        data = backup.read_bytes()
        if not sqlite_summary.is_sqlite(data):
            raise DecryptError(f"{backup.name} is encrypted: give the key with --key-file")
    else:
        data, header = decrypt(backup, key)
    workdir.write_private(db_path, data)
    workdir.write_private(run / "schema.sql", sqlite_summary.schema_sql(db_path).encode())
    return describe(db_path, source=backup.name, header=header), run
