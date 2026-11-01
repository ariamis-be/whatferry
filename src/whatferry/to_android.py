"""Convert an iPhone WhatsApp account's history into an Android account's msgstore.db.

The reverse of convert.py. Input: the iPhone account's ChatStorage.sqlite
(from a checked backup), a way to read its media files out of the backup,
and a decrypted copy of the Android account's msgstore.db (WhatsApp's own
backup of the account the chats move into, which is the template: right
schema, right version). Output, in a new private run folder: a merged
msgstore.db, the media laid out as WhatsApp for Android keeps it
(Media/WhatsApp Images/Sent/IMG-20261025-WF0001.jpg …), and a report. Nothing
here writes to a phone or a backup.

How rows are filled follows what WhatsApp for Android itself writes, as
measured on a real msgstore.db (WhatsApp 2.26.41): times in
milliseconds; sort_id orders a chat's messages; received 1:1 messages have
sender 0 and group ones point at the member's jid row; received_timestamp is
the message time on received messages and 0 on sent ones; a visible chat has
its last, display and read pointers on its newest message; media sit in a
folder per kind, with Sent/ for your own, and keep MIME type, base64 SHA-256
and size. Values WhatsApp sets the same on (nearly) every row are copied as
constants.

Converted: text, images, videos, audio and voice notes, documents, GIFs,
stickers, locations, contact cards and deleted-message placeholders. Not
converted yet: replies, reactions, polls, calls and system notices.
"""

import base64
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable

from whatferry import compat, schema, sqlite_summary, workdir
from whatferry.convert import APPLE_EPOCH, ConvertError, compatible

# iPhone ZMESSAGETYPE -> Android message_type (convert.TYPES, the other way round).
TYPES = {
    0: 0,    # text
    1: 1,    # image
    2: 3,    # video
    3: 2,    # audio and voice notes
    4: 4,    # contact card
    5: 5,    # location
    8: 9,    # document
    11: 13,  # GIF
    14: 15,  # deleted ("This message was deleted")
    15: 20,  # sticker
}
MEDIA_TYPES = {1, 2, 3, 9, 13, 20}  # Android types with a message_media row
SENT, RECEIVED = 13, 0  # status: read by the other side / received

# What WhatsApp for Android writes on (nearly) every row of each kind.
MESSAGE_CONSTANTS = {
    "broadcast": 0, "origination_flags": 0, "origin": 0, "lookup_tables": 0, "message_add_on_flags": 0,
    "view_mode": 0, "receipt_server_timestamp": -1, "starred": 0,
}
CHAT_CONSTANTS = {
    "hidden": 0, "archived": 0, "plaintext_disabled": 1, "spam_detection": 1, "chat_origin": "general",
    "group_type": 0, "unseen_message_count": 0, "unseen_row_count": 0, "unseen_missed_calls_count": 0,
    "unseen_earliest_message_received_time": 0, "unseen_important_message_count": 0, "show_group_description": 0,
    "ephemeral_expiration": 0, "participation_status": 0, "history_sync_progress": 0, "chat_lock": 0,
    "vcard_ui_dismissed": 0,
}
MEDIA_CONSTANTS = {"transferred": 1, "autotransfer_retry_enabled": 1, "transcoded": 0, "suspicious_content": 0,
                   "has_streaming_sidecar": 0}
# jid.type for each server, as WhatsApp numbers them.
JID_TYPES = {"s.whatsapp.net": 0, "g.us": 1, "lid": 18}

# Where each kind of file goes under Media/, its name prefix, and the
# extension when the iPhone's file has none.
FOLDERS = {
    1: ("WhatsApp Images", "IMG", ".jpg"),
    3: ("WhatsApp Video", "VID", ".mp4"),
    2: ("WhatsApp Audio", "AUD", ".m4a"),
    9: ("WhatsApp Documents", "DOC", ""),
    13: ("WhatsApp Animated Gifs", "VID", ".mp4"),
    20: ("WhatsApp Stickers", "STK", ".webp"),
}
VOICE = ("WhatsApp Voice Notes", "PTT", ".opus")

MediaReader = Callable[[str], bytes | None]


@dataclass
class Report:
    iphone_messages: int = 0
    converted: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    already_there: int = 0
    chats_matched: int = 0
    chats_created: int = 0
    groups_created: int = 0
    members_created: int = 0
    media_rows: int = 0
    media_files_copied: int = 0
    media_files_missing: int = 0
    checks: dict[str, object] = field(default_factory=dict)
    # The same checks on the Android database as WhatsApp left it: its own
    # quirks (messages of deleted chats, arrival order) aren't the conversion's.
    checks_before: dict[str, object] = field(default_factory=dict)
    output: str = ""
    # SHA-256 of the Android database the history was merged into: the
    # writer refuses an Android backup that no longer matches it.
    source_sha256: str = ""
    account_folder: str | None = None
    direction: str = "iphone-to-android"
    compatibility: list[dict] = field(default_factory=list)
    # Columns whatferry doesn't know, filled with the value WhatsApp's own rows agree on.
    filled: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def android_ms(seconds: float | None) -> int | None:
    return round((seconds + APPLE_EPOCH) * 1000) if seconds else None


class Target:
    """Write-side helpers over the copy of the Android msgstore.db."""

    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.columns = {t: {r[1] for r in self.db.execute(f"PRAGMA table_info('{t}')")}
                        for t in ("message", "chat", "jid", "message_media", "message_location", "message_vcard",
                                  "group_participant_user", "jid_map")}
        # One row per person or group: WhatsApp also keeps a row per linked
        # device (agent or device not 0) for the same user, which no chat uses.
        device = " AND ".join(f"coalesce({c}, 0) = 0" for c in ("agent", "device") if c in self.columns["jid"])
        self.jids = {(r["user"], r["server"]): r["_id"] for r in self.db.execute(
            f"SELECT _id, user, server FROM jid {'WHERE ' + device if device else ''} ORDER BY _id DESC")}
        self.lid_of = {phone: lid for lid, phone in self.db.execute("SELECT lid_row_id, jid_row_id FROM jid_map")} \
            if self.columns["jid_map"] else {}
        self.phone_of = {lid: phone for phone, lid in self.lid_of.items()}
        self.chats = {r["jid_row_id"]: r["_id"] for r in self.db.execute("SELECT _id, jid_row_id FROM chat")}
        self.keys = {(r[0], r[1], r[2]) for r in self.db.execute("SELECT chat_row_id, from_me, key_id FROM message")}
        self.members = {(r[0], r[1]) for r in self.db.execute(
            "SELECT group_jid_row_id, user_jid_row_id FROM group_participant_user")}
        # File names already used. New files also say WF where WhatsApp says WA, so they
        # can't share a name with a file WhatsApp made (it finds media by file_path).
        self.names = {PurePosixPath(r[0]).name for r in self.db.execute(
            "SELECT file_path FROM message_media WHERE file_path IS NOT NULL")}
        # Columns newer than whatferry's snapshots, filled the way WhatsApp's own rows are.
        known = schema.known_columns("android")
        self.fill = {t: schema.neighbour_values(self.db, t, known.get(t)) for t, cols in self.columns.items() if cols}

    def insert(self, table: str, values: dict) -> int:
        """Insert what this WhatsApp version has columns for; returns the new row id."""
        values = {k: v for k, v in (self.fill.get(table, {}) | values).items() if k in self.columns[table]}
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        return self.db.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values())).lastrowid

    def jid(self, jid: str) -> int:
        user, _, server = jid.partition("@")
        if (user, server) not in self.jids:
            self.jids[(user, server)] = self.insert("jid", {
                "user": user, "server": server, "agent": 0, "device": 0, "type": JID_TYPES.get(server, 0),
                "raw_string": jid})
        return self.jids[(user, server)]


class Source:
    """Read-side helpers over the iPhone account's ChatStorage.sqlite."""

    def __init__(self, path: Path):
        self.db = sqlite3.connect(sqlite_summary.read_only_uri(path), uri=True)
        self.db.row_factory = sqlite3.Row
        self.members = {r["Z_PK"]: r["ZMEMBERJID"] for r in self.db.execute("SELECT Z_PK, ZMEMBERJID FROM ZWAGROUPMEMBER")}


def convert(ios_db: Path, android_db: Path, media: MediaReader | None, account_folder: str | None = None,
            android_app: str | None = None) -> tuple[Report, Path]:
    """Merge the iPhone history into a copy of the Android account's msgstore.db."""
    checked = compatible(compat.check_ios(ios_db, compat.IOS_READ),
                         compat.check_android(android_db, android_app, compat.ANDROID_WRITE))
    run = workdir.new_run("to-android")
    out = run / "files"
    out.mkdir(mode=0o700)
    merged = out / "msgstore.db"
    report = Report(output=str(run), source_sha256=workdir.copy_private(android_db, merged),
                    account_folder=account_folder, compatibility=checked)
    with sqlite_summary.open_read_only(android_db) as before:
        report.checks_before = check(before)
    source = Source(ios_db)
    target = Target(merged)
    report.filled = {f"{t}.{c}": v for t, values in target.fill.items() for c, v in values.items()}
    with closing(source.db), closing(target.db):
        target.db.execute("BEGIN")
        chats = _chats(source, target, report)
        touched = _messages(source, target, chats, media, out, report)
        _resort(target, touched)
        _chat_summaries(target, touched)
        target.db.commit()
        report.checks = check(target.db)
    workdir.write_private(run / "report.json", json.dumps(report.as_dict(), indent=2).encode())
    return report, run


def _chats(source: Source, target: Target, report: Report) -> dict[int, int]:
    """iPhone ZWACHATSESSION pk -> Android chat _id, matching by jid (or the privacy ID it maps to) or creating."""
    out: dict[int, int] = {}
    kinds = ", ".join(str(t) for t in TYPES)
    sessions = source.db.execute(
        "SELECT s.Z_PK, s.ZCONTACTJID, s.ZPARTNERNAME, s.ZSESSIONTYPE, s.ZARCHIVED FROM ZWACHATSESSION s "
        f"WHERE s.ZSESSIONTYPE IN (0, 1) AND EXISTS (SELECT 1 FROM ZWAMESSAGE m WHERE m.ZCHATSESSION = s.Z_PK "
        f"AND m.ZMESSAGETYPE IN ({kinds}) AND m.ZSTANZAID IS NOT NULL AND m.ZMESSAGEDATE > 0)").fetchall()
    for session in sessions:
        jid = session["ZCONTACTJID"]
        if not jid or "@" not in jid:
            continue
        group = jid.endswith("@g.us")
        jid_row = target.jid(jid)
        # The chat may be kept under the person's number or their privacy ID
        # (@lid), and the iPhone may name it by either.
        lid_row = target.lid_of.get(jid_row)
        phone_row = target.phone_of.get(jid_row)
        existing = next((target.chats[r] for r in (jid_row, lid_row, phone_row) if r and r in target.chats), None)
        if existing:
            if existing not in out.values():
                report.chats_matched += 1
            out[session["Z_PK"]] = existing
            continue
        first = source.db.execute("SELECT min(ZMESSAGEDATE) FROM ZWAMESSAGE WHERE ZCHATSESSION = ? AND ZMESSAGEDATE > 0",
                                  (session["Z_PK"],)).fetchone()[0]
        chat = target.insert("chat", CHAT_CONSTANTS | {
            "jid_row_id": jid_row, "subject": session["ZPARTNERNAME"] if group else None,
            "archived": int(bool(session["ZARCHIVED"])), "created_timestamp": android_ms(first),
            # WhatsApp points a chat at the contact's privacy ID when it knows it.
            "account_jid_row_id": lid_row or jid_row,
        })
        target.chats[jid_row] = chat
        report.chats_created += 1
        if group:
            report.groups_created += 1
            _participants(source, target, session["Z_PK"], jid_row, report)
        out[session["Z_PK"]] = chat
    return out


def _participants(source: Source, target: Target, session: int, group_row: int, report: Report) -> None:
    for (member,) in source.db.execute(
            "SELECT ZMEMBERJID FROM ZWAGROUPMEMBER WHERE ZCHATSESSION = ? AND ZMEMBERJID IS NOT NULL "
            "AND coalesce(ZISACTIVE, 1) = 1", (session,)):
        user_row = target.jid(member)
        if (group_row, user_row) not in target.members:
            target.insert("group_participant_user", {"group_jid_row_id": group_row, "user_jid_row_id": user_row,
                                                     "rank": 0, "pending": 0})
            target.members.add((group_row, user_row))
            report.members_created += 1


def _messages(source: Source, target: Target, chats: dict[int, int], media: MediaReader | None, out: Path,
              report: Report) -> list[int]:
    rows = source.db.execute(
        "SELECT m.Z_PK, m.ZCHATSESSION, m.ZISFROMME, m.ZMESSAGEDATE, m.ZMESSAGETYPE, m.ZTEXT, m.ZSTANZAID, "
        "m.ZGROUPMEMBER, m.ZSTARRED, m.ZFROMJID, i.ZMEDIALOCALPATH, i.ZTITLE, i.ZVCARDSTRING, i.ZVCARDNAME, "
        "i.ZLATITUDE, i.ZLONGITUDE, i.ZMOVIEDURATION, i.ZFILESIZE FROM ZWAMESSAGE m "
        "LEFT JOIN ZWAMEDIAITEM i ON i.Z_PK = m.ZMEDIAITEM ORDER BY m.ZCHATSESSION, m.ZMESSAGEDATE, m.Z_PK").fetchall()
    converted, skipped = Counter(), Counter()
    touched = set()
    group_sizes = Counter(g for g, _ in target.members)
    chat_jid = {chat: jid for jid, chat in target.chats.items()}
    servers = {row: server for (_, server), row in target.jids.items()}
    numbers = defaultdict(int)
    for m in rows:
        report.iphone_messages += 1
        kind = TYPES.get(m["ZMESSAGETYPE"])
        chat = chats.get(m["ZCHATSESSION"])
        if kind is None or chat is None or not m["ZSTANZAID"] or not m["ZMESSAGEDATE"]:
            skipped[str(m["ZMESSAGETYPE"])] += 1
            continue
        from_me = int(bool(m["ZISFROMME"]))
        if (chat, from_me, m["ZSTANZAID"]) in target.keys:
            report.already_there += 1
            continue
        group = servers.get(chat_jid.get(chat)) == "g.us"
        sender = 0
        if group and not from_me:
            member = source.members.get(m["ZGROUPMEMBER"]) or (
                m["ZFROMJID"] if m["ZFROMJID"] and not m["ZFROMJID"].endswith("@g.us") else None)
            sender = target.jid(member) if member else 0
        ms = android_ms(m["ZMESSAGEDATE"])
        text = m["ZTEXT"] if kind == 0 else (m["ZTITLE"] if kind in (1, 3, 13) else None)
        if kind == 4:
            text = m["ZVCARDNAME"]
        row = target.insert("message", MESSAGE_CONSTANTS | {
            "chat_row_id": chat, "from_me": from_me, "key_id": m["ZSTANZAID"], "sender_jid_row_id": sender,
            "status": SENT if from_me else RECEIVED, "timestamp": ms, "received_timestamp": 0 if from_me else ms,
            "recipient_count": group_sizes.get(chat_jid.get(chat), 0) if group else 0, "message_type": kind,
            "text_data": text, "starred": int(bool(m["ZSTARRED"])), "sort_id": 0,
        })
        target.keys.add((chat, from_me, m["ZSTANZAID"]))
        touched.add(chat)
        if kind in MEDIA_TYPES:
            _media(target, m, row, chat, kind, from_me, ms, media, out, numbers, report)
        elif kind == 5:
            target.insert("message_location", {"message_row_id": row, "chat_row_id": chat, "latitude": m["ZLATITUDE"],
                                               "longitude": m["ZLONGITUDE"], "place_name": m["ZTITLE"],
                                               "map_download_status": 0})
        elif kind == 4 and m["ZVCARDSTRING"]:
            target.insert("message_vcard", {"message_row_id": row, "vcard": m["ZVCARDSTRING"]})
        converted[str(kind)] += 1
    report.converted = dict(converted)
    report.skipped = dict(skipped)
    return sorted(touched)


def _media(target: Target, m, row: int, chat: int, kind: int, from_me: int, ms: int, media: MediaReader | None,
           out: Path, numbers: dict, report: Report) -> None:
    local = m["ZMEDIALOCALPATH"]
    data = media(local) if media and local else None
    suffix = PurePosixPath(local).suffix.lower() if local else ""
    values = MEDIA_CONSTANTS | {
        "message_row_id": row, "chat_row_id": chat, "mime_type": m["ZVCARDSTRING"],
        "media_duration": int(m["ZMOVIEDURATION"] or 0) if kind in (2, 3, 13) else None,
        "media_name": m["ZTITLE"] if kind == 9 else None,
    }
    if kind == 1 and m["ZLATITUDE"]:
        # The iPhone keeps an image's size in the location columns.
        values |= {"width": int(m["ZLATITUDE"]), "height": int(m["ZLONGITUDE"] or 0)}
    if data is None:
        if local:
            report.media_files_missing += 1
        values |= {"transferred": 0, "file_size": m["ZFILESIZE"], "file_length": m["ZFILESIZE"],
                   "file_hash": m["ZVCARDNAME"]}
    else:
        rel = _place(target, data, kind, from_me, ms, suffix, m["ZTITLE"], out, numbers)
        values |= {"file_path": rel, "file_size": len(data), "file_length": len(data),
                   "file_hash": base64.b64encode(hashlib.sha256(data).digest()).decode()}
        report.media_files_copied += 1
    target.insert("message_media", values)
    report.media_rows += 1


def _place(target: Target, data: bytes, kind: int, from_me: int, ms: int, suffix: str, title: str | None, out: Path,
           numbers: dict) -> str:
    """Write one file where WhatsApp for Android keeps it; returns its file_path."""
    # WhatsApp names files by the phone's own date: this computer's time zone stands in for it.
    day = datetime.fromtimestamp(ms / 1000, UTC).astimezone()
    folder, prefix, default = VOICE if kind == 2 and suffix == ".opus" else FOLDERS[kind]
    parts = [folder]
    if prefix == "PTT":
        parts.append(day.strftime("%G%V"))  # voice notes go in ISO week folders: the week's own year
    elif from_me:
        parts.append("Sent")
    if kind == 9 and title and PurePosixPath(title).name == title and not title.startswith("."):
        name = title  # documents keep their own name
        stem, ext = PurePosixPath(title).stem, PurePosixPath(title).suffix
        n = 1
        while name in target.names:
            n += 1
            name = f"{stem} ({n}){ext}"
    else:
        date = day.strftime("%Y%m%d")
        while True:
            numbers[(prefix, date)] += 1
            name = f"{prefix}-{date}-WF{numbers[(prefix, date)]:04d}{suffix or default}"
            if name not in target.names:
                break
    target.names.add(name)
    rel = PurePosixPath("Media", *parts, name)
    path = out / Path(*rel.parts)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    workdir.write_private(path, data)
    return str(rel)


def _resort(target: Target, chats: list[int]) -> None:
    """sort_id orders a chat's messages: renumber each touched chat by time, reusing its own numbers.

    The chat's existing sort ids, and for each new row a number above every
    sort id and row id in the database, are handed out again in time order:
    they stay unique across chats, and the history lands in place even when
    it's older than what the chat already has.
    """
    fresh = target.db.execute("SELECT max(coalesce(max(sort_id), 0), max(_id)) FROM message").fetchone()[0] or 0
    for chat in chats:
        rows = target.db.execute("SELECT _id, sort_id FROM message WHERE chat_row_id = ? ORDER BY timestamp, _id",
                                 (chat,)).fetchall()
        pool = []
        for r in rows:
            if not r["sort_id"]:
                fresh += 1
            pool.append(r["sort_id"] or fresh)
        pool.sort()
        target.db.executemany("UPDATE message SET sort_id = ? WHERE _id = ?",
                              [(sort, r["_id"]) for sort, r in zip(pool, rows)])


def _chat_summaries(target: Target, chats: list[int]) -> None:
    for chat in chats:
        last = target.db.execute("SELECT _id, sort_id, timestamp FROM message WHERE chat_row_id = ? "
                                 "ORDER BY sort_id DESC LIMIT 1", (chat,)).fetchone()
        values = {"last_message_row_id": last["_id"], "display_message_row_id": last["_id"],
                  "last_read_message_row_id": last["_id"], "last_read_receipt_sent_message_row_id": last["_id"],
                  "last_message_sort_id": last["sort_id"], "display_message_sort_id": last["sort_id"],
                  "last_read_message_sort_id": last["sort_id"], "last_read_receipt_sent_message_sort_id": last["sort_id"],
                  "sort_timestamp": last["timestamp"], "hidden": 0}
        values = {k: v for k, v in values.items() if k in target.columns["chat"]}
        target.db.execute(f"UPDATE chat SET {', '.join(f'{k} = ?' for k in values)} WHERE _id = ?",
                          [*values.values(), chat])


def check(db: sqlite3.Connection) -> dict[str, object]:
    """Consistency of the merged database: what WhatsApp would trip over first."""
    one = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "integrity": one("PRAGMA integrity_check"),
        "messages without a chat": one("SELECT count(*) FROM message m LEFT JOIN chat c ON c._id = m.chat_row_id "
                                       "WHERE c._id IS NULL"),
        "media rows without a message": one("SELECT count(*) FROM message_media mm LEFT JOIN message m "
                                            "ON m._id = mm.message_row_id WHERE m._id IS NULL"),
        "duplicate message ids in a chat": one("SELECT count(*) FROM (SELECT 1 FROM message GROUP BY chat_row_id, "
                                               "from_me, key_id HAVING count(*) > 1)"),
        "duplicate sort ids": one("SELECT count(*) FROM (SELECT 1 FROM message WHERE sort_id > 0 GROUP BY sort_id "
                                  "HAVING count(*) > 1)"),
        "sort out of time order": one(
            "SELECT count(*) FROM (SELECT timestamp, lag(timestamp) OVER (PARTITION BY chat_row_id ORDER BY sort_id) "
            "AS before FROM message) WHERE timestamp < before"),
        "chats pointing at a missing message": one(
            "SELECT count(*) FROM chat c WHERE c.last_message_row_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM message m WHERE m._id = c.last_message_row_id)"),
        "messages": one("SELECT count(*) FROM message"),
        "chats": one("SELECT count(*) FROM chat WHERE hidden = 0"),
        "first message": _date(one("SELECT min(timestamp) FROM message WHERE timestamp > 0")),
        "last message": _date(one("SELECT max(timestamp) FROM message")),
    }


def _date(ms) -> str | None:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="seconds") if ms else None


def backup_media(backup, account_folder: str | None) -> MediaReader:
    """Read the account's media files out of an iPhone backup by their ZMEDIALOCALPATH."""
    from whatferry.ios import SHARED_DOMAIN
    from whatferry.ios_backup import FILE

    prefix = f"{account_folder}/" if account_folder else ""
    entries = {e.path: e for e in backup.entries() if e.domain == SHARED_DOMAIN and e.flags == FILE
               and e.path.startswith(f"{prefix}Message/")}

    def read(local: str) -> bytes | None:
        entry = entries.get(f"{prefix}Message/{local.lstrip('/')}")
        return backup.read(entry) if entry else None

    return read


__all__ = ["ConvertError", "Report", "backup_media", "check", "convert"]
