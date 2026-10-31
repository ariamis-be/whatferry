"""Snapshots of WhatsApp's database structure, and what changed between them.

A snapshot holds a database's shape and nothing it stores: tables, columns
(type, NOT NULL, default), indexes, triggers and views, plus the iPhone's
Core Data entities and model version or Android's PRAGMA user_version. That
makes it safe to commit. The ones whatferry was measured on live in
schemas/ios and schemas/android beside this file, one per distinct shape,
named by its fingerprint, each listing the app versions it was seen with.

A database is "tested" when its shape is one of those, or differs only in
ways that can't matter to the conversion. Every difference is sorted:

- harmless: a table or column the conversion doesn't touch, a new table;
- review: something on a table the conversion writes changed, but not so it
  must fail (a new nullable column, a changed default, a new index), or the
  database version moved: the conversion runs, and the preview gets a closer
  look before writing;
- stop: a column or table the conversion uses is gone, a table it writes
  gained a NOT NULL column with no default, a unique index or a trigger, or
  an entity it writes was renamed. The conversion refuses and names it.

After a WhatsApp update, `whatferry schema capture` on a fresh database
records the new shape (see schemas/CHANGES.md for the routine).
"""

import hashlib
import json
import plistlib
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from whatferry import sqlite_summary

STORE = Path(__file__).parent / "schemas"
HARMLESS, REVIEW, STOP = "harmless", "review", "stop"
# The Core Data entities the iPhone side writes rows of (convert.Target).
IOS_ENTITIES = {"WAChatSession", "WAMessage", "WAMediaItem", "WAGroupMember", "WAGroupInfo"}


class SchemaError(Exception):
    pass


@dataclass
class Change:
    level: str
    what: str

    def as_dict(self) -> dict:
        return asdict(self)


def capture(path: Path) -> dict:
    """The structure of a WhatsApp database: ios (ChatStorage.sqlite) or android (msgstore.db)."""
    if not Path(path).is_file():
        raise FileNotFoundError(f"no database at {path}")
    with sqlite_summary.open_read_only(path) as db:
        try:
            master = db.execute("SELECT type, name, tbl_name, sql FROM sqlite_master "
                                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
        except sqlite3.DatabaseError as e:
            raise SchemaError(f"{path} is not a database ({e})") from e
        names = {r[1] for r in master if r[0] == "table"}
        kind = "ios" if "ZWAMESSAGE" in names else "android" if "message" in names else None
        if kind is None:
            raise SchemaError(f"{path} is not a WhatsApp ChatStorage.sqlite or msgstore.db")
        tables = {}
        for type_, name, _, sql in master:
            if type_ != "table":
                continue
            columns = {r[1]: {"type": r[2], "notnull": bool(r[3]), "default": r[4], "pk": bool(r[5])}
                       for r in db.execute(f"PRAGMA table_info('{name}')")}
            # A virtual table's columns come from its module; its SQL says which.
            tables[name] = {"columns": columns} | ({"virtual": sql} if sql and sql.upper().startswith("CREATE VIRTUAL") else {})
        snap = {
            "kind": kind,
            "tables": tables,
            "indexes": {n: {"table": t, "unique": _unique(db, n), "sql": s} for type_, n, t, s in master
                        if type_ == "index" and s},
            "triggers": {n: {"table": t, "sql": s} for type_, n, t, s in master if type_ == "trigger"},
            "views": sorted(n for type_, n, _, _ in master if type_ == "view"),
        }
        if kind == "ios":
            snap["entities"] = dict(sorted((r[1], r[0]) for r in db.execute("SELECT Z_ENT, Z_NAME FROM Z_PRIMARYKEY")))
            snap["version"] = model_version(db)
        else:
            snap["version"] = db.execute("PRAGMA user_version").fetchone()[0]
    return snap


def _unique(db: sqlite3.Connection, index: str) -> bool:
    row = db.execute("SELECT \"unique\" FROM pragma_index_list((SELECT tbl_name FROM sqlite_master WHERE name = ?)) "
                     "WHERE name = ?", (index, index)).fetchone()
    return bool(row and row[0])


def model_version(db: sqlite3.Connection) -> str | None:
    """Core Data's model identifiers from ChatStorage's metadata ("2.12.14")."""
    try:
        meta = plistlib.loads(db.execute("SELECT Z_PLIST FROM Z_METADATA").fetchone()[0])
    except (sqlite3.Error, TypeError, plistlib.InvalidFileException):
        return None
    return ", ".join(map(str, meta.get("NSStoreModelVersionIdentifiers") or [])) or None


def fingerprint(snap: dict) -> str:
    """The same for two databases of the same shape, whatever app version made them."""
    shape = {k: v for k, v in snap.items() if k not in ("seen", "fingerprint")}
    return hashlib.sha256(json.dumps(shape, sort_keys=True).encode()).hexdigest()[:16]


def known(kind: str, store: Path | None = None) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(((store or STORE) / kind).glob("*.json"))]


def save(snap: dict, app_version: str | None = None, store: Path | None = None, today: date | None = None) -> tuple[Path, bool]:
    """Record a snapshot, or the app version it was seen with again. Returns (file, whether the shape is new)."""
    fp = fingerprint(snap)
    path = (store or STORE) / snap["kind"] / f"{fp}.json"
    new = not path.exists()
    saved = snap | {"fingerprint": fp, "seen": []} if new else json.loads(path.read_text())
    seen = {"app": app_version, "captured": (today or date.today()).isoformat()}
    if not any(s.get("app") == app_version for s in saved["seen"]):
        saved["seen"].append(seen)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, indent=1, sort_keys=True) + "\n")
    return path, new


def diff(old: dict, new: dict, uses: dict | None = None, writes: set[str] = frozenset()) -> list[Change]:
    """What changed from old to new, each sorted by what it means to a conversion.

    `uses` is a compat.py table -> columns map (None: the table is optional);
    `writes`, the tables the conversion inserts into.
    """
    uses = uses or {}
    out: list[Change] = []
    add = lambda level, what: out.append(Change(level, what))
    used = lambda table, column=None: table in uses and (column is None or column in (uses[table] or ()))

    for table in sorted(old["tables"].keys() - new["tables"].keys()):
        add(STOP if used(table) and uses[table] is not None else REVIEW if used(table) else HARMLESS,
            f"table {table} dropped")
    for table in sorted(new["tables"].keys() - old["tables"].keys()):
        add(HARMLESS, f"table {table} added")
    for table in sorted(old["tables"].keys() & new["tables"].keys()):
        was, now = old["tables"][table]["columns"], new["tables"][table]["columns"]
        written = table in writes
        for column in sorted(was.keys() - now.keys()):
            add(STOP if used(table, column) else HARMLESS, f"{table}.{column} dropped")
        for column in sorted(now.keys() - was.keys()):
            c = now[column]
            if written and c["notnull"] and c["default"] is None and not c["pk"]:
                add(STOP, f"{table}.{column} added, NOT NULL with no default")
            else:
                add(REVIEW if written else HARMLESS, f"{table}.{column} added" +
                    (" (filled like WhatsApp's own rows where they agree)" if written else ""))
        for column in sorted(was.keys() & now.keys()):
            a, b = was[column], now[column]
            for prop in ("type", "notnull", "default", "pk"):
                if a[prop] == b[prop]:
                    continue
                level = HARMLESS
                if written and prop == "notnull" and b["notnull"] and b["default"] is None \
                        and not used(table, column):
                    level = STOP
                elif used(table, column) or written:
                    level = REVIEW
                add(level, f"{table}.{column} {prop} {a[prop]!r} -> {b[prop]!r}")
    for kind, label in (("indexes", "index"), ("triggers", "trigger")):
        was, now = old.get(kind, {}), new.get(kind, {})
        for name in sorted(now.keys() - was.keys()):
            entry = now[name]
            written = entry["table"] in writes
            blocks = written and (kind == "triggers" or entry.get("unique"))
            add(STOP if blocks else REVIEW if written else HARMLESS,
                f"{'unique ' if entry.get('unique') else ''}{label} {name} on {entry['table']} added")
        for name in sorted(was.keys() - now.keys()):
            add(REVIEW if was[name]["table"] in writes else HARMLESS, f"{label} {name} on {was[name]['table']} dropped")
        for name in sorted(was.keys() & now.keys()):
            if was[name]["sql"] != now[name]["sql"]:
                written = now[name]["table"] in writes
                add(STOP if written and kind == "triggers" else REVIEW if written else HARMLESS, f"{label} {name} changed")
    if "entities" in old or "entities" in new:
        was, now = old.get("entities", {}), new.get("entities", {})
        writing = IOS_ENTITIES if writes else set()
        for name in sorted(was.keys() - now.keys()):
            add(STOP if name in writing else HARMLESS, f"entity {name} gone")
        for name in sorted(now.keys() - was.keys()):
            add(HARMLESS, f"entity {name} added")
        # Entity numbers are read from Z_PRIMARYKEY on every run, so renumbering is fine.
        for name in sorted(was.keys() & now.keys()):
            if was[name] != now[name]:
                add(HARMLESS, f"entity {name} renumbered {was[name]} -> {now[name]}")
    # A new database version means WhatsApp migrated it: what a value means may
    # have changed even where the layout didn't.
    if old.get("version") != new.get("version"):
        add(REVIEW, f"database version {old.get('version')} -> {new.get('version')}")
    return out


def closest(snap: dict, uses: dict | None = None, writes: set[str] = frozenset(),
            store: Path | None = None) -> tuple[dict | None, list[Change]]:
    """The known snapshot this database differs least from, and how."""
    rank = {STOP: 0, REVIEW: 1, HARMLESS: 2}
    best, best_changes, best_key = None, [], None
    for candidate in known(snap["kind"], store):
        changes = diff(candidate, snap, uses, writes)
        counts = Counter(c.level for c in changes)
        key = (counts[STOP], counts[REVIEW], counts[HARMLESS])
        if best_key is None or key < best_key:
            best, best_changes, best_key = candidate, changes, key
    return best, sorted(best_changes, key=lambda c: rank[c.level])


def known_columns(kind: str, store: Path | None = None) -> dict[str, set[str]]:
    """Every column a known snapshot has, per table: anything else is new since whatferry was measured."""
    out: dict[str, set[str]] = {}
    for snap in known(kind, store):
        for table, t in snap["tables"].items():
            out.setdefault(table, set()).update(t["columns"])
    return out


def neighbour_values(db: sqlite3.Connection, table: str, known: set[str] | None, share: float = 0.9,
                     at_least: int = 10) -> dict[str, object]:
    """Columns this WhatsApp has that whatferry wasn't measured on, filled the way WhatsApp fills them.

    For each such column, the value WhatsApp's own rows agree on (at least
    `share` of them, out of `at_least` rows or more); a column they don't
    agree on is left to its default.
    """
    if known is None:
        return {}
    columns = [r[1] for r in db.execute(f"PRAGMA table_info('{table}')") if r[1] not in known and not r[5]]
    if not columns:
        return {}
    rows = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    if rows < at_least:
        return {}
    out = {}
    for column in columns:
        value, n = db.execute(f'SELECT "{column}", count(*) n FROM {table} GROUP BY 1 ORDER BY n DESC LIMIT 1').fetchone()
        if value is not None and n >= share * rows:
            out[column] = value
    return out
