"""Did the chats arrive: a fingerprint of each side, and what differs between two.

A fingerprint lists every message whatferry carries across, keyed by
WhatsApp's own message ID (Android key_id, iPhone ZSTANZAID), which both
converters keep. For each: its chat, kind (in iPhone terms), time to the
millisecond, a hash of its text or caption, and a hash of its media file.
Given a way to read the files, the media hash is of the file itself, so a
file that didn't arrive shows; without, it is the hash the database records.

What whatferry doesn't carry is counted apart and never fails a run: those
are the known losses (calls, system messages, polls and the other kinds
without a counterpart; reactions and quoted replies are not messages of
their own, so they never enter the fingerprint). A passing run diffs to zero.

Chats are named by the last four digits of their ID only. Texts are hashed;
the kit's seed corpus is the only content that ever passes through here.
"""

import base64
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from whatferry import convert, sqlite_summary
from whatferry.to_android import android_ms

# Message kinds both converters carry, in iPhone ZMESSAGETYPE terms.
CARRIED = set(convert.TYPES.values())
MEDIA = {1, 2, 3, 8, 11, 15}
CAPTIONED = {1, 2, 11}  # image, video, GIF: the caption is converted both ways
CONTACT = 4

KNOWN_LOSSES = {
    "system": "group events, security-code changes and other system lines",
    "call": "voice and video calls",
    "poll": "polls",
    "other": "kinds whatferry has no counterpart for yet",
    "reactions": "reactions (not messages of their own: never in the fingerprint)",
    "quoted replies": "the link to the quoted message (the reply's own text is compared)",
}
ANDROID_LOSS_NAMES = {7: "system", 8: "call", 10: "call", 46: "poll", 66: "poll"}
IOS_LOSS_NAMES = {6: "system", 10: "system", 59: "call", 46: "poll", 66: "poll"}

MediaReader = Callable[[str], bytes | None]
FIELDS = ("chat", "kind", "at_ms", "text", "media")


def _hash(text: str | None) -> str | None:
    return hashlib.sha256(text.encode()).hexdigest()[:16] if text else None


def _file_hash(data: bytes | None) -> str | None:
    return base64.b64encode(hashlib.sha256(data).digest()).decode() if data is not None else None


def chat_label(jid: str | None) -> str:
    """A chat named by its last four digits and server, plus a short hash so two chats never share a name."""
    if not jid:
        return "?"
    user, _, server = jid.partition("@")
    return f"…{user[-4:]}@{server}#{hashlib.sha256(jid.encode()).hexdigest()[:6]}"


def _item(chat, kind, at_ms, text, media) -> dict:
    return {"chat": chat_label(chat), "kind": kind, "at_ms": at_ms, "text": _hash(text), "media": media}


def ios(db: Path, media: MediaReader | None = None) -> dict:
    """One iPhone account's ChatStorage.sqlite; media read by ZMEDIALOCALPATH (to_android.backup_media)."""
    items, losses = {}, Counter()
    with sqlite_summary.open_read_only(db) as con:
        rows = con.execute(
            "SELECT m.ZSTANZAID, m.ZISFROMME, m.ZMESSAGETYPE, m.ZMESSAGEDATE, m.ZTEXT, c.ZCONTACTJID, "
            "i.ZTITLE, i.ZVCARDNAME, i.ZMEDIALOCALPATH FROM ZWAMESSAGE m "
            "JOIN ZWACHATSESSION c ON c.Z_PK = m.ZCHATSESSION LEFT JOIN ZWAMEDIAITEM i ON i.Z_PK = m.ZMEDIAITEM "
            "WHERE c.ZSESSIONTYPE IN (?, ?)", (convert.SESSION_1TO1, convert.SESSION_GROUP)).fetchall()
    for stanza, from_me, kind, date, text, jid, title, vcard_name, local in rows:
        if kind not in CARRIED or not stanza or not date:
            losses[IOS_LOSS_NAMES.get(kind, "other")] += 1
            continue
        shown = text if kind == 0 else title if kind in CAPTIONED else vcard_name if kind == CONTACT else None
        file = None
        if kind in MEDIA:
            file = (_file_hash(media(local)) if local else None) if media else vcard_name
        items[f"{int(bool(from_me))}:{stanza}"] = _item(jid, kind, android_ms(date), shown, file)
    return {"items": items, "losses": dict(losses)}


def android(db: Path, media_root: Path | None = None) -> dict:
    """A decrypted msgstore.db; media from a copy of WhatsApp's Media folder (Device.pull_media)."""
    items, losses = {}, Counter()
    with sqlite_summary.open_read_only(db) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        jids = {r[0]: f"{r[1]}@{r[2]}" for r in con.execute("SELECT _id, user, server FROM jid")}
        phone_of = {}
        if "jid_map" in tables:
            phone_of = {jids.get(lid): jids.get(pn) for lid, pn in con.execute(
                "SELECT lid_row_id, jid_row_id FROM jid_map")}
        media_cols = {r[1] for r in con.execute("PRAGMA table_info(message_media)")} if "message_media" in tables \
            else set()
        # Columns come and go between WhatsApp versions: read what's there.
        picked = ", ".join(f"mm.{c}" if c in media_cols else "NULL" for c in ("media_caption", "file_path", "file_hash"))
        join = "LEFT JOIN message_media mm ON mm.message_row_id = m._id" if media_cols else ""
        rows = con.execute(
            f"SELECT m.key_id, m.from_me, m.message_type, m.timestamp, m.text_data, c.jid_row_id, {picked} "
            f"FROM message m JOIN chat c ON c._id = m.chat_row_id {join}").fetchall()
    for key_id, from_me, android_type, ms, text, chat_row, media_caption, file_path, file_hash in rows:
        jid = jids.get(chat_row)
        if not jid or jid.endswith(("@broadcast", "@temp")):
            continue
        jid = phone_of.get(jid) or jid
        kind = convert.TYPES.get(android_type)
        if kind is None or not key_id or not ms:
            losses[ANDROID_LOSS_NAMES.get(android_type, "other")] += 1
            continue
        shown = text if kind in (0, CONTACT) else (text or media_caption) if kind in CAPTIONED else None
        file = None
        if kind in MEDIA:
            if media_root is None:
                file = file_hash
            elif file_path:
                source = convert._media_source(media_root, file_path)
                file = _file_hash(source.read_bytes()) if source.is_file() else None
        items[f"{int(bool(from_me))}:{key_id}"] = _item(jid, kind, ms, shown, file)
    return {"items": items, "losses": dict(losses)}


def diff(seed: dict, result: dict, examples: int = 20) -> dict:
    """What the result lacks, has extra, or has different, message by message."""
    s, r = seed["items"], result["items"]
    missing = sorted(k for k in s if k not in r)
    extra = sorted(k for k in r if k not in s)
    changed, changed_keys = Counter(), []
    for key in sorted(s.keys() & r.keys()):
        fields = [f for f in FIELDS if s[key][f] != r[key][f]]
        changed.update(fields)
        if fields:
            changed_keys.append(key)
    missing_by_chat = Counter(s[k]["chat"] for k in missing)
    return {
        "passed": not missing and not extra and not changed_keys,
        "seed": len(s), "result": len(r), "missing": len(missing), "extra": len(extra),
        "changed": dict(changed), "missing_by_chat": dict(missing_by_chat),
        "examples": {"missing": missing[:examples], "extra": extra[:examples], "changed": changed_keys[:examples]},
        "known_losses": {"seed": seed.get("losses", {}), "result": result.get("losses", {})},
    }


def has_text(fingerprint: dict, text: str) -> bool:
    """Whether a text message with exactly this text is in the fingerprint."""
    wanted = _hash(text)
    return any(item["kind"] == 0 and item["text"] == wanted for item in fingerprint["items"].values())


def summary(d: dict) -> str:
    if d["passed"]:
        return f"{d['seed']} messages, all arrived unchanged"
    parts = [f"{d['missing']} missing" if d["missing"] else "", f"{d['extra']} extra" if d["extra"] else "",
             ", ".join(f"{n} with a different {f}" for f, n in d["changed"].items())]
    return f"{d['seed']} messages: " + "; ".join(p for p in parts if p)


def save(fingerprint: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fingerprint, indent=1, sort_keys=True))
    path.chmod(0o600)
    return path


def load(path: Path) -> dict:
    return json.loads(path.read_text())


__all__ = ["KNOWN_LOSSES", "android", "chat_label", "diff", "ios", "load", "save", "summary"]
