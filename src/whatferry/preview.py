"""What a conversion will put on the iPhone, read back from the merged database.

The merged copy is exactly what `ios write` puts into the backup, so this is
the result as the phone will have it: every chat, which ones the Android
history joins or adds, and the messages themselves.

Names come from the iPhone account's own ContactsV2.sqlite (WhatsApp's copy
of the address book), as the app would show them. Unlike everything else
whatferry reports, this holds names and message text: it goes only to the
local page that asked, never into state.json, a report or the summary.
"""

import base64
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from whatferry import sqlite_summary
from whatferry.convert import APPLE_EPOCH, SESSION_GROUP, SESSION_1TO1

# WhatsApp for iOS message types, as the page labels them.
KINDS = {0: "text", 1: "image", 2: "video", 3: "audio", 4: "contact", 5: "location", 6: "system", 7: "link",
         8: "document", 10: "system", 11: "gif", 14: "deleted", 15: "sticker"}
# Shown as pictures in the preview; the rest by their kind.
PICTURES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}
PICTURE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
                 ".gif": "image/gif", ".heic": "image/heic"}
MAX_PICTURE = 15 * 1024 * 1024
MAX_MESSAGES = 200


class PreviewError(Exception):
    """The preview can't be read; the message says why."""


@dataclass
class Chat:
    id: int
    name: str
    jid: str
    group: bool
    # "new" (only Android history), "joined" (on the iPhone already, Android
    # history added) or "unchanged" (iPhone only).
    change: str
    messages: int
    from_android: int
    first: str | None
    last: str | None


@dataclass
class Message:
    id: int
    at: str | None
    from_me: bool
    sender: str | None
    kind: str
    text: str | None
    from_android: bool
    picture: bool


def _iso(seconds) -> str | None:
    return datetime.fromtimestamp(seconds + APPLE_EPOCH, UTC).isoformat(timespec="seconds") if seconds else None


def _number(jid: str | None) -> str:
    user = (jid or "").split("@")[0]
    return f"+{user}" if user.isdigit() else user or "?"


def contact_names(*contacts_dbs: Path) -> dict[str, str]:
    """WhatsApp ID (and privacy ID) → the name the iPhone shows; earlier databases win."""
    names: dict[str, str] = {}
    for path in reversed([p for p in contacts_dbs if p and p.is_file()]):
        try:
            with sqlite_summary.open_read_only(path) as db:
                rows = db.execute("SELECT ZWHATSAPPID, ZLID, coalesce(nullif(ZFULLNAME, ''), nullif(ZBUSINESSNAME, ''), "
                                  "nullif(ZGIVENNAME, '')) FROM ZWAADDRESSBOOKCONTACT").fetchall()
        except sqlite3.Error:
            continue
        for jid, lid, name in rows:
            if not name:
                continue
            if jid:
                names[jid] = name
            if lid:
                names[lid if "@" in lid else f"{lid}@lid"] = name
    return names


class Preview:
    """The merged database next to the one it was merged into."""

    def __init__(self, merged: Path, original: Path, names: dict[str, str], media_root: Path):
        if not merged.is_file() or not original.is_file():
            raise PreviewError("the conversion's files are gone: convert again")
        self.merged, self.names, self.media_root = merged, names, media_root
        with sqlite_summary.open_read_only(original) as db:
            self.original_chats = {r[0] for r in db.execute("SELECT Z_PK FROM ZWACHATSESSION")}
            # Converted rows are added after every row the iPhone had.
            self.original_max = db.execute("SELECT coalesce(max(Z_PK), 0) FROM ZWAMESSAGE").fetchone()[0]

    def _open(self):
        return sqlite_summary.open_read_only(self.merged)

    def chats(self) -> list[dict]:
        with self._open() as db:
            rows = db.execute(
                "SELECT c.Z_PK, c.ZCONTACTJID, c.ZPARTNERNAME, c.ZSESSIONTYPE, count(m.Z_PK), "
                "coalesce(sum(m.Z_PK > ?), 0), min(nullif(m.ZMESSAGEDATE, 0)), max(m.ZMESSAGEDATE) "
                "FROM ZWACHATSESSION c LEFT JOIN ZWAMESSAGE m ON m.ZCHATSESSION = c.Z_PK "
                "WHERE c.ZSESSIONTYPE IN (?, ?) GROUP BY c.Z_PK ORDER BY max(m.ZMESSAGEDATE) DESC",
                (self.original_max, SESSION_1TO1, SESSION_GROUP)).fetchall()
        out = []
        for pk, jid, partner, kind, total, added, first, last in rows:
            group = kind == SESSION_GROUP
            change = "new" if pk not in self.original_chats else "joined" if added else "unchanged"
            name = (partner if group else None) or self.names.get(jid) or partner or _number(jid)
            out.append(asdict(Chat(pk, name, jid, group, change, total, added, _iso(first), _iso(last))))
        return out

    def messages(self, chat: int, limit: int = 60) -> list[dict]:
        """The chat's newest messages, oldest first, as the iPhone will show them."""
        limit = max(1, min(int(limit), MAX_MESSAGES))
        with self._open() as db:
            rows = db.execute(
                "SELECT m.Z_PK, m.ZMESSAGEDATE, m.ZISFROMME, m.ZMESSAGETYPE, m.ZTEXT, m.ZPUSHNAME, "
                "g.ZMEMBERJID, g.ZCONTACTNAME, i.ZTITLE, i.ZMEDIALOCALPATH, m.ZFROMJID "
                "FROM ZWAMESSAGE m LEFT JOIN ZWAGROUPMEMBER g ON g.Z_PK = m.ZGROUPMEMBER "
                "LEFT JOIN ZWAMEDIAITEM i ON i.Z_PK = m.ZMEDIAITEM "
                "WHERE m.ZCHATSESSION = ? ORDER BY m.ZSORT DESC, m.Z_PK DESC LIMIT ?", (chat, limit)).fetchall()
        out = []
        for pk, at, from_me, kind, text, push, member, member_name, caption, local, from_jid in reversed(rows):
            sender = None
            if not from_me:
                who = member or from_jid
                sender = self.names.get(who) or member_name or push or _number(who)
            android = pk > self.original_max
            picture = bool(android and local and Path(local).suffix.lower() in PICTURES)
            out.append(asdict(Message(pk, _iso(at), bool(from_me), sender, KINDS.get(kind, "other"),
                                      text or caption, android, picture)))
        return out

    def picture(self, message: int) -> str:
        """A converted picture as a data: URL (the page's CSP allows those, not other origins)."""
        with self._open() as db:
            row = db.execute("SELECT i.ZMEDIALOCALPATH FROM ZWAMESSAGE m JOIN ZWAMEDIAITEM i ON i.Z_PK = m.ZMEDIAITEM "
                             "WHERE m.Z_PK = ? AND m.Z_PK > ?", (message, self.original_max)).fetchone()
        if not row or not row[0]:
            raise PreviewError("no converted picture for that message")
        root = self.media_root.resolve()
        path = (root / row[0]).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() not in PICTURES or not path.is_file():
            raise PreviewError("no converted picture for that message")
        if path.stat().st_size > MAX_PICTURE:
            raise PreviewError("that picture is too large to preview")
        data = base64.b64encode(path.read_bytes()).decode()
        return f"data:{PICTURE_TYPES[path.suffix.lower()]};base64,{data}"
