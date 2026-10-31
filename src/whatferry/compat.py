"""Is a WhatsApp database the shape whatferry was built against? Checked before converting.

The converters fill rows the way WhatsApp itself does, as measured on real
databases. A newer WhatsApp can rename or drop a column: finding that up
front gives a clear refusal instead of a failure half-way. Beyond the columns
used, the whole structure is compared with the snapshots whatferry was
measured on (schema.py): a change that must break the conversion refuses it,
one that might matters flags it, so the preview gets a closer look before
anything is written, and the rest pass. The app version itself doesn't
count: WhatsApp ships every week, and most releases leave the database as it
was.
"""

import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

from whatferry import schema, sqlite_summary

# The columns each direction reads or writes, per table. A table listed with
# None is optional: used when present. Android -> iPhone reads ANDROID_READ
# and writes IOS_WRITE; iPhone -> Android reads IOS_READ and writes ANDROID_WRITE.
ANDROID_READ = {
    "message": {"_id", "chat_row_id", "from_me", "key_id", "sender_jid_row_id", "timestamp", "message_type",
                "text_data", "starred"},
    "chat": {"_id", "jid_row_id", "subject", "archived", "created_timestamp"},
    "jid": {"_id", "user", "server", "raw_string"},
    "props": {"key", "value"},
    "message_media": None,
    "message_location": None,
    "message_vcard": None,
    "jid_map": None,
}
IOS_READ = {
    "ZWACHATSESSION": {"Z_PK", "ZCONTACTJID", "ZPARTNERNAME", "ZSESSIONTYPE", "ZARCHIVED"},
    "ZWAMESSAGE": {"Z_PK", "ZCHATSESSION", "ZISFROMME", "ZMESSAGEDATE", "ZMESSAGETYPE", "ZTEXT", "ZSTANZAID",
                   "ZGROUPMEMBER", "ZMEDIAITEM", "ZSTARRED", "ZFROMJID"},
    "ZWAMEDIAITEM": {"Z_PK", "ZMEDIALOCALPATH", "ZTITLE", "ZVCARDSTRING", "ZVCARDNAME", "ZLATITUDE", "ZLONGITUDE",
                     "ZMOVIEDURATION", "ZFILESIZE"},
    "ZWAGROUPMEMBER": {"Z_PK", "ZMEMBERJID", "ZCHATSESSION"},
    "ZWAGROUPINFO": None,
}
IOS_WRITE = {
    "Z_PRIMARYKEY": {"Z_ENT", "Z_NAME", "Z_MAX"},
    "ZWACHATSESSION": {"Z_PK", "Z_ENT", "Z_OPT", "ZARCHIVED", "ZCONTACTABID", "ZCONTACTJID", "ZFLAGS", "ZGROUPINFO",
                       "ZHIDDEN", "ZIDENTITYVERIFICATIONEPOCH", "ZIDENTITYVERIFICATIONSTATE", "ZLASTMESSAGE",
                       "ZLASTMESSAGEDATE", "ZLASTMESSAGETEXT", "ZMESSAGECOUNTER", "ZPARTNERNAME", "ZREMOVED",
                       "ZSESSIONTYPE", "ZSPOTLIGHTSTATUS", "ZUNREADCOUNT"},
    "ZWAMESSAGE": {"Z_PK", "Z_ENT", "Z_OPT", "ZCHATSESSION", "ZCHILDMESSAGESDELIVEREDCOUNT", "ZCHILDMESSAGESPLAYEDCOUNT",
                   "ZCHILDMESSAGESREADCOUNT", "ZDATAITEMVERSION", "ZENCRETRYCOUNT", "ZFILTEREDRECIPIENTCOUNT", "ZFLAGS",
                   "ZFROMJID", "ZGROUPEVENTTYPE", "ZGROUPMEMBER", "ZISFROMME", "ZMEDIAITEM", "ZMESSAGEDATE",
                   "ZMESSAGEERRORSTATUS", "ZMESSAGESTATUS", "ZMESSAGETYPE", "ZPUSHNAME", "ZSORT", "ZSPOTLIGHTSTATUS",
                   "ZSTANZAID", "ZSTARRED", "ZTEXT", "ZTOJID"},
    "ZWAMEDIAITEM": {"Z_PK", "Z_ENT", "Z_OPT", "ZASPECTRATIO", "ZFILESIZE", "ZHACCURACY", "ZLATITUDE", "ZLONGITUDE",
                     "ZMEDIALOCALPATH", "ZMEDIAORIGIN", "ZMESSAGE", "ZMOVIEDURATION", "ZTITLE", "ZVCARDNAME",
                     "ZVCARDSTRING"},
    "ZWAGROUPMEMBER": {"Z_PK", "Z_ENT", "Z_OPT", "ZCHATSESSION", "ZCONTACTABID", "ZCONTACTNAME", "ZISACTIVE",
                       "ZISADMIN", "ZMEMBERJID"},
    "ZWAGROUPINFO": {"Z_PK", "Z_ENT", "Z_OPT", "ZCHATSESSION", "ZCREATIONDATE", "ZSTATE"},
}
ANDROID_WRITE = {
    "message": {"_id", "chat_row_id", "from_me", "key_id", "sender_jid_row_id", "status", "broadcast",
                "recipient_count", "origination_flags", "origin", "timestamp", "received_timestamp",
                "receipt_server_timestamp", "message_type", "text_data", "starred", "lookup_tables",
                "message_add_on_flags", "view_mode", "sort_id"},
    "chat": {"_id", "jid_row_id", "hidden", "subject", "created_timestamp", "display_message_row_id",
             "last_message_row_id", "last_read_message_row_id", "last_read_receipt_sent_message_row_id", "archived",
             "sort_timestamp", "plaintext_disabled", "spam_detection", "unseen_message_count", "unseen_row_count",
             "last_message_sort_id", "display_message_sort_id", "last_read_message_sort_id"},
    "jid": {"_id", "user", "server", "agent", "device", "type", "raw_string"},
    "message_media": {"message_row_id", "chat_row_id", "transferred", "file_path", "file_size", "file_length",
                      "mime_type", "file_hash", "width", "height", "media_duration", "media_name", "media_caption"},
    "message_location": {"message_row_id", "chat_row_id", "latitude", "longitude", "place_name"},
    "message_vcard": {"message_row_id", "vcard"},
    "group_participant_user": {"group_jid_row_id", "user_jid_row_id", "rank", "pending"},
    "props": {"key", "value"},
    "jid_map": None,
}


@dataclass
class Compat:
    kind: str
    missing: list[str] = field(default_factory=list)
    version: str | None = None
    tested: bool = False
    note: str | None = None
    # This database's structure (schema.fingerprint), the known snapshot it
    # is closest to, and what differs from it that matters (review or stop).
    shape: str | None = None
    closest: str | None = None
    changes: list[dict] = field(default_factory=list)

    @property
    def blocking(self) -> list[str]:
        return [c["what"] for c in self.changes if c["level"] == schema.STOP]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.blocking

    def as_dict(self) -> dict:
        return asdict(self) | {"ok": self.ok}


def _missing(db: sqlite3.Connection, needs: dict) -> list[str]:
    out = []
    for table, columns in needs.items():
        have = {r[1] for r in db.execute(f"PRAGMA table_info('{table}')")}
        if not have:
            if columns is not None:
                out.append(f"table {table}")
            continue
        out += [f"{table}.{c}" for c in sorted((columns or set()) - have)]
    return out


def _shape(result: Compat, path: Path, needs: dict, writes: bool, store: Path) -> None:
    """Compare the structure with the known snapshots: tested when nothing that matters moved."""
    snap = schema.capture(path)
    result.shape = schema.fingerprint(snap)
    closest, changes = schema.closest(snap, needs, set(needs) if writes else set(), store)
    result.closest = closest["fingerprint"] if closest else None
    result.changes = [c.as_dict() for c in changes if c.level != schema.HARMLESS]
    result.tested = closest is not None and not result.changes


def check_ios(path: Path, needs: dict = IOS_WRITE, store: Path | None = None) -> Compat:
    """An iPhone ChatStorage.sqlite: the columns used, its Core Data model version, and its structure."""
    result = Compat("iPhone")
    with sqlite_summary.open_read_only(path) as db:
        result.missing = _missing(db, needs)
        result.version = schema.model_version(db)
    if "table ZWAMESSAGE" in result.missing:
        result.note = "not a WhatsApp ChatStorage database"
        return result
    _shape(result, path, needs, needs is IOS_WRITE, store)
    result.note = _note(result, "iOS", f"WhatsApp for iOS with database model {result.version or 'unknown'}")
    return result


def check_android(path: Path, app_version: str | None = None, needs: dict = ANDROID_READ,
                  store: Path | None = None) -> Compat:
    """A decrypted msgstore.db: the columns used, its database and app versions, and its structure."""
    result = Compat("Android")
    with sqlite_summary.open_read_only(path) as db:
        result.missing = _missing(db, needs)
        user_version = db.execute("PRAGMA user_version").fetchone()[0]
    result.version = (f"WhatsApp {app_version}, " if app_version else "") + f"database version {user_version}"
    if "table message" in result.missing:
        result.note = "not a WhatsApp msgstore database"
        return result
    _shape(result, path, needs, needs is ANDROID_WRITE, store)
    result.note = _note(result, "Android", result.version)
    return result


def _note(result: Compat, platform: str, made_by: str) -> str | None:
    if result.missing or result.blocking:
        found = [f"missing {m}" for m in result.missing] + result.blocking
        return f"WhatsApp for {platform} stores this differently from the version whatferry knows ({_list(found)})"
    if result.tested:
        return None
    if result.closest is None:
        return f"made by {made_by}; whatferry has no record of this database layout. Look through the preview before writing"
    return (f"made by {made_by}, laid out differently from the databases whatferry was checked on "
            f"({_list([c['what'] for c in result.changes])}). Look through the preview before writing")


def _list(items: list[str], shown: int = 6) -> str:
    more = len(items) - shown
    return ", ".join(items[:shown]) + (f" and {more} more" if more > 0 else "")
