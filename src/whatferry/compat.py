"""Is a WhatsApp database the shape whatferry was built against? Checked before converting.

The converters fill rows the way WhatsApp itself does, as measured on real
databases of the versions below. A newer WhatsApp can rename or drop a
column: finding that up front gives a clear refusal instead of a failure
half-way. A version other than the measured ones still converts, but is
flagged, so the preview gets a closer look before anything is written.
"""

import plistlib
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

from whatferry import sqlite_summary

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

# What whatferry was measured on. Anything else converts with a warning.
TESTED = {
    # Core Data model identifiers in ChatStorage.sqlite's metadata.
    "ios": {"2.12.14"},
    # msgstore.db PRAGMA user_version, and the WhatsApp version in the backup header.
    "android": {1},
    "android_app": {"2.26.41"},
}


@dataclass
class Compat:
    kind: str
    missing: list[str] = field(default_factory=list)
    version: str | None = None
    tested: bool = False
    note: str | None = None

    @property
    def ok(self) -> bool:
        return not self.missing

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


def check_ios(path: Path, needs: dict = IOS_WRITE) -> Compat:
    """An iPhone ChatStorage.sqlite: the columns used, and its Core Data model version."""
    result = Compat("iPhone")
    with sqlite_summary.open_read_only(path) as db:
        result.missing = _missing(db, needs)
        try:
            meta = plistlib.loads(db.execute("SELECT Z_PLIST FROM Z_METADATA").fetchone()[0])
            ids = meta.get("NSStoreModelVersionIdentifiers") or []
            result.version = ", ".join(map(str, ids)) or None
        except (sqlite3.Error, TypeError, plistlib.InvalidFileException):
            result.version = None
    result.tested = bool(result.version) and set(result.version.split(", ")) <= TESTED["ios"]
    if "table ZWAMESSAGE" in result.missing:
        result.note = "not a WhatsApp ChatStorage database"
    elif result.missing:
        result.note = f"WhatsApp for iOS stores this differently from the version whatferry knows ({_list(result.missing)})"
    elif not result.tested:
        result.note = (f"made by WhatsApp for iOS with database model {result.version or 'unknown'}; whatferry was "
                       f"checked on {', '.join(sorted(TESTED['ios']))}. Look through the preview before writing")
    return result


def check_android(path: Path, app_version: str | None = None, needs: dict = ANDROID_READ) -> Compat:
    """A decrypted msgstore.db: the columns used, its database version, and the app version that made it."""
    result = Compat("Android")
    with sqlite_summary.open_read_only(path) as db:
        result.missing = _missing(db, needs)
        user_version = db.execute("PRAGMA user_version").fetchone()[0]
    app = ".".join((app_version or "").split(".")[:3]) or None
    result.version = (f"WhatsApp {app_version}, " if app_version else "") + f"database version {user_version}"
    result.tested = user_version in TESTED["android"] and (app is None or app in TESTED["android_app"])
    if "table message" in result.missing:
        result.note = "not a WhatsApp msgstore database"
    elif result.missing:
        result.note = f"WhatsApp for Android stores this differently from the version whatferry knows ({_list(result.missing)})"
    elif not result.tested:
        result.note = (f"made by {result.version}; whatferry was checked on WhatsApp "
                       f"{', '.join(sorted(TESTED['android_app']))}. Look through the preview before writing")
    return result


def _list(items: list[str], shown: int = 6) -> str:
    more = len(items) - shown
    return "missing " + ", ".join(items[:shown]) + (f" and {more} more" if more > 0 else "")
