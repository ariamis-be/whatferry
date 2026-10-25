"""Map WhatsApp inside an iPhone backup, and compare two backups.

`inspect` answers where WhatsApp keeps its data and what shape the databases
have; `diff` answers which files a change on the phone touched, such as
adding a second account. Both are read-only towards the backup.
"""

import re
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from whatferry import sqlite_summary, workdir
from whatferry.ios_backup import FILE, Backup, DeviceInfo, Entry

# Core Data stores dates as seconds since 2001-01-01 UTC.
APPLE_EPOCH = 978307200

CHAT_STORAGE = "ChatStorage.sqlite"
SHARED_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"
ACCOUNTS_METHOD = 2
SIDECARS = ("-wal", "-shm")

# ChatStorage tables the conversion will have to fill, by what they hold.
COUNTED = {
    "chats": "ZWACHATSESSION",
    "messages": "ZWAMESSAGE",
    "media": "ZWAMEDIAITEM",
    "group members": "ZWAGROUPMEMBER",
    "group info": "ZWAGROUPINFO",
    "message info (receipts)": "ZWAMESSAGEINFO",
    "profile push names": "ZWAPROFILEPUSHNAME",
}


@dataclass
class Database:
    domain: str
    path: str
    size: int
    user_version: int
    tables: int
    extracted_to: str
    counts: dict[str, int | None] = field(default_factory=dict)
    core_data_entities: dict[str, int] = field(default_factory=dict)
    first_message: str | None = None
    last_message: str | None = None


@dataclass
class Account:
    """A WhatsApp account on the iPhone, by its last digits only (two of the ID, four of the number)."""
    id_ends: str
    number_ends: str | None
    country: str | None
    main: bool  # owns the ChatStorage.sqlite at the root of the shared folder


@dataclass
class AccountFolder:
    folder: str
    has_chat_database: bool


@dataclass
class Report:
    device: DeviceInfo
    domains: dict[str, dict[str, int]] = field(default_factory=dict)
    top_folders: dict[str, dict[str, int]] = field(default_factory=dict)
    databases: list[Database] = field(default_factory=list)
    accounts: list[Account] = field(default_factory=list)
    account_folders: list[AccountFolder] = field(default_factory=list)
    # Bumped whenever account detection changes, so older saved checks can be
    # told apart: 1 read the keyboard file (wrong), 2 does not.
    accounts_method: int = ACCOUNTS_METHOD

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def chat_storages(self) -> list[Database]:
        return [d for d in self.databases if Path(d.path).name == CHAT_STORAGE]


def inspect(backup: Backup) -> tuple[Report, Path]:
    run = workdir.new_run("ios")
    entries = backup.entries()
    report = Report(device=backup.info)

    files = [e for e in entries if e.flags == FILE]
    for domain in sorted({e.domain for e in entries}):
        mine = [e for e in files if e.domain == domain]
        report.domains[domain] = {"files": len(mine), "bytes": sum(e.size for e in mine)}
        folders = Counter(e.path.split("/", 1)[0] if "/" in e.path else "." for e in mine)
        report.top_folders[domain] = dict(folders.most_common())

    by_key = {e.key: e for e in files}
    extracted: dict[tuple[str, str], Path] = {}
    for entry in files:
        if not entry.path.endswith((".sqlite", ".db")):
            continue
        data = backup.read(entry)
        if not sqlite_summary.is_sqlite(data):
            continue
        target = _extract_database(backup, entry, data, by_key, run)
        extracted[entry.key] = target
        summary = sqlite_summary.summarise(target)
        db = Database(domain=entry.domain, path=entry.path, size=entry.size,
                      user_version=summary.user_version, tables=len(summary.tables),
                      extracted_to=str(target))
        if Path(entry.path).name == CHAT_STORAGE:
            _describe_chat_storage(target, summary, db)
        schema = target.with_name(target.name + ".schema.sql")
        workdir.write_private(schema, sqlite_summary.schema_sql(target).encode())
        report.databases.append(db)
    report.accounts = _accounts(extracted)
    report.account_folders = _account_folders(files)
    return report, run


# The main account's WhatsApp ID ("LID", a privacy ID, not a phone number)
# is the single row of ChatStorage's push-name table: the account's own
# profile name. LID.sqlite pairs IDs with phone numbers. Neither is
# documented, so both may be missing.
#
# Not used: UITextInputContextIdentifiers.plist. Its ID_<lid>@lid keys
# looked like one per account, but they are the keyboard language per chat:
# checked on a real backup, one belonged to a contact with 2,185 messages.
# Further accounts are only visible as data/<id>/ folders (see
# _account_folders), with no number to read.


def _accounts(extracted: dict) -> list[Account]:
    main = _main_account_id(extracted.get((SHARED_DOMAIN, CHAT_STORAGE)))
    if not main:
        return []
    number_ends, country = _numbers(extracted.get((SHARED_DOMAIN, "LID.sqlite")), [main]).get(main, (None, None))
    return [Account(id_ends=main[-2:], number_ends=number_ends, country=country, main=True)]


def _main_account_id(chat_storage: Path | None) -> str | None:
    if not chat_storage:
        return None
    try:
        with sqlite_summary.open_read_only(chat_storage) as db:
            rows = db.execute("SELECT ZJID FROM ZWAPROFILEPUSHNAME WHERE ZJID LIKE '%@lid' LIMIT 2").fetchall()
    except sqlite3.Error:
        return None
    return rows[0][0].split("@")[0] if len(rows) == 1 else None


def _numbers(lid_db: Path | None, ids: list[str]) -> dict[str, tuple[str | None, str | None]]:
    """Last two digits and country of each ID's phone number, where known."""
    if not lid_db or not ids:
        return {}
    out = {}
    try:
        with sqlite_summary.open_read_only(lid_db) as db:
            for i in ids:
                row = db.execute("SELECT ZPHONENUMBER, ZCOUNTRYCODE FROM ZWAZACCOUNT WHERE ZIDENTIFIER = ?",
                                 (f"{i}@lid",)).fetchone()
                if row and row[0]:
                    digits = re.sub(r"\D", "", str(row[0]))
                    out[i] = (digits[-4:] if len(digits) >= 4 else None, row[1])
    except sqlite3.Error:
        return {}
    return out


def _account_folders(files: list[Entry]) -> list[AccountFolder]:
    """The data/<id>/ folders WhatsApp keeps for further accounts."""
    folders: dict[str, bool] = {}
    for e in files:
        if e.domain != SHARED_DOMAIN:
            continue
        m = re.match(r"^(data/[0-9A-Fa-f-]{36})/(.*)$", e.path)
        if m:
            folders[m.group(1)] = folders.get(m.group(1), False) or m.group(2) == CHAT_STORAGE
    return [AccountFolder(f, has) for f, has in sorted(folders.items())]


def _extract_database(backup: Backup, entry: Entry, data: bytes, by_key: dict, run: Path) -> Path:
    """Copy a database and its WAL out of the backup, then fold the WAL in.

    WhatsApp runs SQLite in WAL mode, so recent changes may exist only in the
    -wal file beside the database. Checkpointing the private copy makes it
    whole; the backup itself is never opened for writing.
    """
    target = run / "files" / workdir.safe_relative(entry.domain) / workdir.safe_relative(entry.path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    workdir.write_private(target, data)
    for suffix in SIDECARS:
        sidecar = by_key.get((entry.domain, entry.path + suffix))
        if sidecar:
            workdir.write_private(target.with_name(target.name + suffix), backup.read(sidecar))
    with closing(sqlite3.connect(target)) as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.execute("PRAGMA journal_mode = DELETE")
    return target


def _describe_chat_storage(path: Path, summary: sqlite_summary.Summary, db: Database) -> None:
    db.counts = {label: summary.rows(table) for label, table in COUNTED.items()}
    with sqlite_summary.open_read_only(path) as conn:
        if summary.table("Z_PRIMARYKEY"):
            db.core_data_entities = dict(conn.execute("SELECT Z_NAME, Z_MAX FROM Z_PRIMARYKEY ORDER BY Z_NAME"))
        message = summary.table("ZWAMESSAGE")
        if message and "ZMESSAGEDATE" in message.columns:
            first, last = conn.execute(
                "SELECT min(ZMESSAGEDATE), max(ZMESSAGEDATE) FROM ZWAMESSAGE WHERE ZMESSAGEDATE > 0").fetchone()
            db.first_message = _iso_from_apple(first)
            db.last_message = _iso_from_apple(last)


def _iso_from_apple(seconds: float | None) -> str | None:
    if not seconds:
        return None
    return datetime.fromtimestamp(seconds + APPLE_EPOCH, UTC).isoformat(timespec="seconds")


@dataclass
class Diff:
    added: list[Entry] = field(default_factory=list)
    removed: list[Entry] = field(default_factory=list)
    changed: list[tuple[Entry, Entry]] = field(default_factory=list)

    def by_folder(self) -> dict[str, Counter]:
        """Counts of added/removed/changed per domain and top-level folder."""
        out: dict[str, Counter] = defaultdict(Counter)
        for kind, items in (("added", self.added), ("removed", self.removed),
                            ("changed", [after for _, after in self.changed])):
            for e in items:
                folder = e.path.split("/", 1)[0] if "/" in e.path else "."
                out[f"{e.domain}  {folder}/"][kind] += 1
        return dict(sorted(out.items()))


def diff(before: Backup, after: Backup) -> Diff:
    old = {e.key: e for e in before.entries()}
    new = {e.key: e for e in after.entries()}
    result = Diff(
        added=[new[k] for k in sorted(new.keys() - old.keys())],
        removed=[old[k] for k in sorted(old.keys() - new.keys())],
    )
    for k in sorted(old.keys() & new.keys()):
        a, b = old[k], new[k]
        if (a.flags, a.size, a.mtime) != (b.flags, b.size, b.mtime):
            result.changed.append((a, b))
    return result
