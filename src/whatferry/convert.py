"""Convert an Android WhatsApp account's history into an iPhone account's chat database.

Input: the decrypted Android msgstore.db, the folder holding that account's
WhatsApp/Media files, and a copy of the target iPhone account's
ChatStorage.sqlite (from a checked backup). Output, in a new private run
folder: a merged ChatStorage.sqlite, the media files laid out the way the
iPhone keeps them (Message/Media/<chat>/<x>/<y>/<uuid>.<ext>), and a report.
Nothing here writes to a phone or a backup; putting the result back is a
separate step.

How rows are filled follows what WhatsApp itself writes, as measured on a
real iPhone (483,345 messages): received 1:1 messages carry the chat's JID
in ZFROMJID, sent ones in ZTOJID; group messages name the group, and
received ones point at a ZWAGROUPMEMBER; ZSORT counts up within a chat;
images keep width and height in ZLATITUDE/ZLONGITUDE; captions sit in the
media row's ZTITLE. Values WhatsApp sets the same on (nearly) every row are
copied as constants.

Converted: text, images, videos, audio and voice notes, documents, GIFs,
stickers, locations, contact cards and deleted-message placeholders, into
chats matched by JID (an Android privacy ID, "@lid", is matched by the phone
number it maps to). Not converted yet, and counted in the report: quoted
replies, reactions, polls, calls and system notices.
"""

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from whatferry import sqlite_summary, workdir

APPLE_EPOCH = 978307200

# Android message_type -> iPhone ZMESSAGETYPE.
TYPES = {
    0: 0,    # text
    1: 1,    # image
    3: 2,    # video
    2: 3,    # audio and voice notes
    4: 4,    # contact card
    5: 5,    # location
    9: 8,    # document
    13: 11,  # GIF
    15: 14,  # deleted ("This message was deleted")
    20: 15,  # sticker
}
MEDIA_TYPES = {1, 2, 3, 4, 5, 8, 11, 15}  # iPhone types that have a media row
SESSION_1TO1, SESSION_GROUP = 0, 1

# What WhatsApp writes on (nearly) every row of each kind.
MESSAGE_CONSTANTS = {
    "Z_OPT": 2, "ZCHILDMESSAGESDELIVEREDCOUNT": 0, "ZCHILDMESSAGESPLAYEDCOUNT": 0, "ZCHILDMESSAGESREADCOUNT": 0,
    "ZDATAITEMVERSION": 3, "ZENCRETRYCOUNT": 0, "ZFILTEREDRECIPIENTCOUNT": 0, "ZGROUPEVENTTYPE": 2,
    "ZMESSAGEERRORSTATUS": 0, "ZSPOTLIGHTSTATUS": -32768, "ZFLAGS": 16777216,
}
SESSION_CONSTANTS = {
    "Z_OPT": 1, "ZFLAGS": 272, "ZHIDDEN": 0, "ZIDENTITYVERIFICATIONEPOCH": -1, "ZIDENTITYVERIFICATIONSTATE": 0,
    "ZREMOVED": 0, "ZSPOTLIGHTSTATUS": -5, "ZUNREADCOUNT": 0, "ZCONTACTABID": 0,
}
MEMBER_CONSTANTS = {"Z_OPT": 1, "ZISADMIN": 0, "ZCONTACTABID": 0}
MEDIA_CONSTANTS = {"Z_OPT": 1, "ZMEDIAORIGIN": 0, "ZHACCURACY": 0.0}
STATUS_SENT, STATUS_RECEIVED = 8, 0


class ConvertError(Exception):
    pass


@dataclass
class Report:
    android_messages: int = 0
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
    not_converted_yet: dict[str, int] = field(default_factory=dict)
    checks: dict[str, object] = field(default_factory=dict)
    output: str = ""
    # SHA-256 of the iPhone database the history was merged into. The backup
    # writer refuses a backup whose database no longer matches it.
    source_sha256: str = ""
    account_folder: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def apple_time(ms: int | None) -> float | None:
    return ms / 1000 - APPLE_EPOCH if ms else None


class Android:
    """Read-side helpers over a decrypted msgstore.db."""

    def __init__(self, path: Path):
        self.db = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        self.db.row_factory = sqlite3.Row
        self.jids = {r["_id"]: r for r in self.db.execute("SELECT _id, user, server, raw_string FROM jid")}
        self.lid_to_phone = dict(self.db.execute("SELECT lid_row_id, jid_row_id FROM jid_map")) \
            if self.table("jid_map") else {}
        self.phone_to_lid = {phone: lid for lid, phone in self.lid_to_phone.items()}
        own = self.db.execute("SELECT value FROM props WHERE key = 'user_push_name'").fetchone()
        self.own_name = own[0] if own else None

    def jid(self, row_id: int | None) -> str | None:
        """A JID as the iPhone writes it; privacy IDs become the phone JID they map to."""
        row = self.jids.get(row_id)
        if row is None:
            return None
        if row["server"] == "lid" and row_id in self.lid_to_phone:
            row = self.jids.get(self.lid_to_phone[row_id], row)
        if row["user"] and row["server"] in ("s.whatsapp.net", "lid", "g.us"):
            return f"{row['user']}@{row['server']}"
        return None

    def lid(self, row_id: int | None) -> str | None:
        """The privacy-ID form of a contact, when Android knows it."""
        row = self.jids.get(row_id)
        if row is None:
            return None
        if row["server"] == "lid":
            return f"{row['user']}@lid"
        lid_row = self.jids.get(self.phone_to_lid.get(row_id))
        return f"{lid_row['user']}@lid" if lid_row else None

    def table(self, name: str) -> bool:
        return self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def display_number(jid: str) -> str:
    user = jid.split("@")[0]
    return f"+{user}" if jid.endswith("@s.whatsapp.net") else user


class Target:
    """Write-side helpers over the copy of the iPhone's ChatStorage.sqlite."""

    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.ent = {r["Z_NAME"]: r["Z_ENT"] for r in self.db.execute("SELECT Z_ENT, Z_NAME FROM Z_PRIMARYKEY")}
        missing = {"WAChatSession", "WAMessage", "WAMediaItem", "WAGroupMember", "WAGroupInfo"} - self.ent.keys()
        if missing:
            raise ConvertError(f"not a WhatsApp ChatStorage database (missing {', '.join(sorted(missing))})")
        self.next_pk = {name: (self.db.execute(f"SELECT max(Z_PK) FROM {table}").fetchone()[0] or 0) + 1
                        for name, table in (("WAChatSession", "ZWACHATSESSION"), ("WAMessage", "ZWAMESSAGE"),
                                            ("WAMediaItem", "ZWAMEDIAITEM"), ("WAGroupMember", "ZWAGROUPMEMBER"),
                                            ("WAGroupInfo", "ZWAGROUPINFO"))}
        self.sessions = {r["ZCONTACTJID"]: r["Z_PK"] for r in self.db.execute("SELECT Z_PK, ZCONTACTJID FROM ZWACHATSESSION")}
        self.members = {(r["ZCHATSESSION"], r["ZMEMBERJID"]): r["Z_PK"]
                        for r in self.db.execute("SELECT Z_PK, ZCHATSESSION, ZMEMBERJID FROM ZWAGROUPMEMBER")}
        self.stanzas = {(r[0], r[1]) for r in self.db.execute("SELECT ZCHATSESSION, ZSTANZAID FROM ZWAMESSAGE")}

    def pk(self, entity: str) -> int:
        value = self.next_pk[entity]
        self.next_pk[entity] += 1
        return value

    def insert(self, table: str, values: dict) -> None:
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        self.db.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))


def convert(android_db: Path, ios_db: Path, media_root: Path | None, account_folder: str | None = None) -> tuple[Report, Path]:
    """Merge the Android history into a copy of the iPhone account's ChatStorage.sqlite."""
    run = workdir.new_run("convert")
    out = run / "files"
    out.mkdir(mode=0o700)
    merged = out / "ChatStorage.sqlite"
    workdir.write_private(merged, ios_db.read_bytes())
    report = Report(output=str(run), source_sha256=hashlib.sha256(ios_db.read_bytes()).hexdigest(),
                    account_folder=account_folder)
    android = Android(android_db)
    target = Target(merged)
    # Files land where the account keeps them: data/<id>/Message/Media for a
    # further account, Message/Media for the main one.
    media_out = out / (account_folder or "") / "Message" / "Media"

    with closing(android.db), closing(target.db):
        target.db.execute("BEGIN")
        sessions = _sessions(android, target, report)
        _messages(android, target, sessions, media_root, media_out, report)
        touched = sorted(set(sessions.values()))
        _resort(target, touched)
        _session_summaries(target, touched)
        _primary_keys(target)
        target.db.commit()
        report.not_converted_yet = _not_converted(android)
        report.checks = check(target.db)
    workdir.write_private(run / "report.json", json.dumps(report.as_dict(), indent=2).encode())
    return report, run


def _sessions(android: Android, target: Target, report: Report) -> dict[int, int]:
    """Android chat row id -> iPhone ZWACHATSESSION pk, matching by JID or creating."""
    out: dict[int, int] = {}
    # Only chats with something to carry over: a chat holding nothing but
    # system notices would arrive on the iPhone empty.
    kinds = ", ".join(str(t) for t in TYPES)
    chats = android.db.execute(
        "SELECT c._id, c.jid_row_id, c.subject, c.archived, c.created_timestamp FROM chat c "
        f"WHERE EXISTS (SELECT 1 FROM message m WHERE m.chat_row_id = c._id AND m.message_type IN ({kinds}) "
        "AND m.key_id IS NOT NULL AND m.timestamp > 0)").fetchall()
    for chat in chats:
        jid = android.jid(chat["jid_row_id"])
        if jid is None or jid.endswith("@broadcast"):
            continue
        group = jid.endswith("@g.us")
        candidates = [jid, android.lid(chat["jid_row_id"])] if not group else [jid]
        existing = next((target.sessions[j] for j in candidates if j and j in target.sessions), None)
        if existing:
            if existing not in out.values():
                report.chats_matched += 1
            out[chat["_id"]] = existing
            continue
        pk = target.pk("WAChatSession")
        target.insert("ZWACHATSESSION", SESSION_CONSTANTS | {
            "Z_PK": pk, "Z_ENT": target.ent["WAChatSession"], "ZARCHIVED": int(bool(chat["archived"])),
            "ZSESSIONTYPE": SESSION_GROUP if group else SESSION_1TO1, "ZMESSAGECOUNTER": 0,
            "ZCONTACTJID": jid, "ZPARTNERNAME": (chat["subject"] if group else None) or display_number(jid),
        })
        target.sessions[jid] = pk
        report.chats_created += 1
        if group:
            info = target.pk("WAGroupInfo")
            target.insert("ZWAGROUPINFO", {
                "Z_PK": info, "Z_ENT": target.ent["WAGroupInfo"], "Z_OPT": 1, "ZSTATE": 0, "ZCHATSESSION": pk,
                "ZCREATIONDATE": apple_time(chat["created_timestamp"]),
            })
            target.db.execute("UPDATE ZWACHATSESSION SET ZGROUPINFO = ? WHERE Z_PK = ?", (info, pk))
            report.groups_created += 1
        out[chat["_id"]] = pk
    return out


def _member(android: Android, target: Target, session: int, sender_row: int, report: Report) -> int | None:
    jid = android.jid(sender_row)
    if jid is None:
        return None
    for candidate in (android.lid(sender_row), jid):
        if candidate and (session, candidate) in target.members:
            return target.members[(session, candidate)]
    pk = target.pk("WAGroupMember")
    # Not in the group's current list: a past member, shown by number.
    target.insert("ZWAGROUPMEMBER", MEMBER_CONSTANTS | {
        "Z_PK": pk, "Z_ENT": target.ent["WAGroupMember"], "ZISACTIVE": 0, "ZCHATSESSION": session,
        "ZMEMBERJID": jid, "ZCONTACTNAME": display_number(jid),
    })
    target.members[(session, jid)] = pk
    report.members_created += 1
    return pk


def _messages(android: Android, target: Target, sessions: dict[int, int], media_root: Path | None,
              media_out: Path, report: Report) -> None:
    has = {t: android.table(t) for t in ("message_media", "message_location", "message_vcard")}
    rows = android.db.execute(
        "SELECT m._id, m.chat_row_id, m.from_me, m.key_id, m.sender_jid_row_id, m.timestamp, m.message_type, "
        "m.text_data, m.starred FROM message m ORDER BY m.chat_row_id, m.timestamp, m._id").fetchall()
    converted, skipped = Counter(), Counter()
    session_jid = {pk: jid for jid, pk in target.sessions.items()}
    for m in rows:
        report.android_messages += 1
        ios_type = TYPES.get(m["message_type"])
        session = sessions.get(m["chat_row_id"])
        if ios_type is None or session is None or not m["key_id"] or not m["timestamp"]:
            skipped[str(m["message_type"])] += 1
            continue
        if (session, m["key_id"]) in target.stanzas:
            report.already_there += 1
            continue
        chat_jid = session_jid[session]
        group = chat_jid.endswith("@g.us")
        from_me = bool(m["from_me"])
        member = None
        if group and not from_me and m["sender_jid_row_id"]:
            member = _member(android, target, session, m["sender_jid_row_id"], report)
        sender_jid = android.jid(m["sender_jid_row_id"]) if group and not from_me else chat_jid
        pk = target.pk("WAMessage")
        values = MESSAGE_CONSTANTS | {
            "Z_PK": pk, "Z_ENT": target.ent["WAMessage"], "ZISFROMME": int(from_me),
            "ZMESSAGESTATUS": STATUS_SENT if from_me else STATUS_RECEIVED, "ZMESSAGETYPE": ios_type,
            "ZCHATSESSION": session, "ZGROUPMEMBER": member, "ZMESSAGEDATE": apple_time(m["timestamp"]),
            "ZFROMJID": None if from_me else chat_jid, "ZTOJID": chat_jid if from_me else None,
            "ZSTANZAID": m["key_id"], "ZSTARRED": 1 if m["starred"] else None,
            "ZPUSHNAME": android.own_name if from_me else display_number(sender_jid or chat_jid),
            "ZTEXT": m["text_data"] if ios_type == 0 else None, "ZSORT": 0,
        }
        target.insert("ZWAMESSAGE", values)
        target.stanzas.add((session, m["key_id"]))
        if ios_type in MEDIA_TYPES:
            media = _media_item(android, target, has, m, pk, ios_type, chat_jid, media_root, media_out, report)
            target.db.execute("UPDATE ZWAMESSAGE SET ZMEDIAITEM = ? WHERE Z_PK = ?", (media, pk))
        converted[str(ios_type)] += 1
    report.converted = dict(converted)
    report.skipped = dict(skipped)


def _media_item(android: Android, target: Target, has: dict, m, message_pk: int, ios_type: int, chat_jid: str,
                media_root: Path | None, media_out: Path, report: Report) -> int:
    pk = target.pk("WAMediaItem")
    row = android.db.execute("SELECT * FROM message_media WHERE message_row_id = ?", (m["_id"],)).fetchone() \
        if has["message_media"] else None
    values = MEDIA_CONSTANTS | {"Z_PK": pk, "Z_ENT": target.ent["WAMediaItem"], "ZMESSAGE": message_pk}
    if row is not None:
        # Columns come and go between WhatsApp versions: read what's there.
        col = dict(row)
        values |= {
            "ZFILESIZE": col.get("file_size") or col.get("file_length"),
            "ZMOVIEDURATION": (col.get("media_duration") or 0) if ios_type in (2, 3) else 0,
            "ZASPECTRATIO": 0.0,
            "ZTITLE": m["text_data"] or col.get("media_caption"),
            # On media rows WhatsApp keeps the MIME type and the file's SHA-256
            # (base64) in the vCard columns; Android records the same hash.
            "ZVCARDSTRING": col.get("mime_type"),
            "ZVCARDNAME": col.get("file_hash"),
        }
        if ios_type == 1 and col.get("width"):
            # WhatsApp keeps an image's size in the location columns.
            values |= {"ZLATITUDE": float(col["width"]), "ZLONGITUDE": float(col.get("height") or 0)}
        if ios_type == 8:
            values["ZTITLE"] = col.get("media_name") or values["ZTITLE"]
        values["ZMEDIALOCALPATH"] = _copy_media(col.get("file_path"), chat_jid, media_root, media_out, report)
        if values["ZMEDIALOCALPATH"] and not values["ZVCARDNAME"]:
            placed = media_out.parent / values["ZMEDIALOCALPATH"]
            values["ZVCARDNAME"] = base64.b64encode(hashlib.sha256(placed.read_bytes()).digest()).decode()
    if ios_type == 5 and has["message_location"]:
        loc = android.db.execute("SELECT latitude, longitude, place_name FROM message_location WHERE message_row_id = ?",
                                 (m["_id"],)).fetchone()
        if loc:
            values |= {"ZLATITUDE": loc["latitude"], "ZLONGITUDE": loc["longitude"], "ZTITLE": loc["place_name"]}
    if ios_type == 4 and has["message_vcard"]:
        card = android.db.execute("SELECT vcard FROM message_vcard WHERE message_row_id = ?", (m["_id"],)).fetchone()
        if card:
            values |= {"ZVCARDSTRING": card["vcard"], "ZVCARDNAME": m["text_data"]}
    target.insert("ZWAMEDIAITEM", values)
    report.media_rows += 1
    return pk


def _media_source(media_root: Path, file_path: str) -> Path:
    """Where a message_media file_path ("Media/WhatsApp Images/…") sits in a copy of the Media folder."""
    return media_root / (file_path.split("/", 1)[1] if file_path.startswith("Media/") else file_path)


def media_found(android_db: Path, media_root: Path, sample: int = 200) -> tuple[int, int]:
    """Of the newest `sample` media files the Android history names, how many this folder has."""
    try:
        with sqlite_summary.open_read_only(android_db) as db:
            paths = [r[0] for r in db.execute("SELECT file_path FROM message_media WHERE file_path IS NOT NULL "
                                              "ORDER BY message_row_id DESC LIMIT ?", (sample,))]
    except sqlite3.Error:
        return 0, 0
    return sum(_media_source(media_root, p).is_file() for p in paths), len(paths)


def _copy_media(file_path: str | None, chat_jid: str, media_root: Path | None, media_out: Path,
                report: Report) -> str | None:
    """Place one file as the iPhone keeps it; returns ZMEDIALOCALPATH, or None if it's missing."""
    if not file_path or media_root is None:
        return None
    source = _media_source(media_root, file_path)
    if not source.is_file():
        report.media_files_missing += 1
        return None
    name = str(uuid.uuid4()).upper()
    rel = Path(chat_jid) / name[0].lower() / name[1].lower() / f"{name}{source.suffix.lower()}"
    target = media_out / rel
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # A hard link costs no space; fall back to a copy across disks.
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    report.media_files_copied += 1
    return str(Path("Media") / rel).replace(os.sep, "/")


def _resort(target: Target, sessions: list[int]) -> None:
    """ZSORT counts up by date within each chat, old history and new rows alike."""
    for session in sessions:
        pks = [r[0] for r in target.db.execute(
            "SELECT Z_PK FROM ZWAMESSAGE WHERE ZCHATSESSION = ? ORDER BY ZMESSAGEDATE, Z_PK", (session,))]
        target.db.executemany("UPDATE ZWAMESSAGE SET ZSORT = ? WHERE Z_PK = ?", [(i, pk) for i, pk in enumerate(pks, 1)])


def _session_summaries(target: Target, sessions: list[int]) -> None:
    for session in sessions:
        last = target.db.execute(
            "SELECT Z_PK, ZMESSAGEDATE, ZTEXT FROM ZWAMESSAGE WHERE ZCHATSESSION = ? ORDER BY ZSORT DESC LIMIT 1",
            (session,)).fetchone()
        if last is None:
            continue  # a chat whose every message was of a kind not converted yet
        count = target.db.execute("SELECT count(*) FROM ZWAMESSAGE WHERE ZCHATSESSION = ?", (session,)).fetchone()[0]
        target.db.execute(
            "UPDATE ZWACHATSESSION SET ZLASTMESSAGE = ?, ZLASTMESSAGEDATE = ?, ZLASTMESSAGETEXT = ?, "
            "ZMESSAGECOUNTER = max(coalesce(ZMESSAGECOUNTER, 0), ?) WHERE Z_PK = ?",
            (last["Z_PK"], last["ZMESSAGEDATE"], last["ZTEXT"] or "", count, session))


def _primary_keys(target: Target) -> None:
    """Core Data hands out the next Z_PK from Z_PRIMARYKEY.Z_MAX: keep it ahead of every row."""
    for name, table in (("WAChatSession", "ZWACHATSESSION"), ("WAMessage", "ZWAMESSAGE"), ("WAMediaItem", "ZWAMEDIAITEM"),
                        ("WAGroupMember", "ZWAGROUPMEMBER"), ("WAGroupInfo", "ZWAGROUPINFO")):
        target.db.execute(f"UPDATE Z_PRIMARYKEY SET Z_MAX = max(Z_MAX, (SELECT coalesce(max(Z_PK), 0) FROM {table})) "
                          "WHERE Z_NAME = ?", (name,))


def _not_converted(android: Android) -> dict[str, int]:
    out = {}
    for label, table in (("quoted replies", "message_quoted"), ("reactions and other add-ons", "message_add_on")):
        if android.table(table):
            out[label] = android.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    return out


def check(db: sqlite3.Connection) -> dict[str, object]:
    """Consistency of the merged database: what WhatsApp would trip over first."""
    one = lambda sql: db.execute(sql).fetchone()[0]
    return {
        "integrity": one("PRAGMA integrity_check"),
        "messages without a chat": one("SELECT count(*) FROM ZWAMESSAGE m LEFT JOIN ZWACHATSESSION c ON c.Z_PK = m.ZCHATSESSION WHERE c.Z_PK IS NULL"),
        "media rows not pointing back": one("SELECT count(*) FROM ZWAMESSAGE m JOIN ZWAMEDIAITEM i ON i.Z_PK = m.ZMEDIAITEM WHERE i.ZMESSAGE != m.Z_PK"),
        "group messages without a member": one(
            "SELECT count(*) FROM ZWAMESSAGE m JOIN ZWACHATSESSION c ON c.Z_PK = m.ZCHATSESSION "
            "WHERE c.ZSESSIONTYPE = 1 AND m.ZISFROMME = 0 AND m.ZGROUPMEMBER IS NULL AND m.ZMESSAGETYPE NOT IN (6, 10)"),
        "duplicate message ids in a chat": one(
            "SELECT count(*) FROM (SELECT 1 FROM ZWAMESSAGE GROUP BY ZCHATSESSION, ZSTANZAID HAVING count(*) > 1)"),
        "sort out of date order": one(
            "SELECT count(*) FROM ZWAMESSAGE a JOIN ZWAMESSAGE b ON a.ZCHATSESSION = b.ZCHATSESSION "
            "AND b.ZSORT = a.ZSORT + 1 WHERE b.ZMESSAGEDATE < a.ZMESSAGEDATE"),
        "primary keys behind rows": one(
            "SELECT count(*) FROM Z_PRIMARYKEY p WHERE p.Z_MAX < CASE p.Z_NAME "
            "WHEN 'WAMessage' THEN (SELECT max(Z_PK) FROM ZWAMESSAGE) "
            "WHEN 'WAChatSession' THEN (SELECT max(Z_PK) FROM ZWACHATSESSION) "
            "WHEN 'WAMediaItem' THEN (SELECT max(Z_PK) FROM ZWAMEDIAITEM) "
            "WHEN 'WAGroupMember' THEN (SELECT max(Z_PK) FROM ZWAGROUPMEMBER) ELSE 0 END"),
        "messages": one("SELECT count(*) FROM ZWAMESSAGE"),
        "chats": one("SELECT count(*) FROM ZWACHATSESSION"),
        "first message": _date(one("SELECT min(ZMESSAGEDATE) FROM ZWAMESSAGE WHERE ZMESSAGEDATE > 0")),
        "last message": _date(one("SELECT max(ZMESSAGEDATE) FROM ZWAMESSAGE")),
    }


def _date(seconds) -> str | None:
    return datetime.fromtimestamp(seconds + APPLE_EPOCH, UTC).isoformat(timespec="seconds") if seconds else None


