"""Describe a SQLite database by its shape, never by its contents.

A summary holds table names, column lists, row counts and the schema's
CREATE statements: enough to plan a conversion, nothing anyone wrote.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Table:
    name: str
    columns: list[str]
    # None when SQLite can't open the table here: a virtual table whose
    # module only exists inside the app, such as WhatsApp's full-text search
    # with its own wa_tokenizer.
    rows: int | None
    virtual: bool = False


@dataclass
class Summary:
    user_version: int
    tables: list[Table] = field(default_factory=list)

    def table(self, name: str) -> Table | None:
        return next((t for t in self.tables if t.name == name), None)

    def rows(self, name: str) -> int | None:
        t = self.table(name)
        return t.rows if t else None


def read_only_uri(path: Path) -> str:
    """A SQLite URI that opens `path` read-only on any platform.

    as_uri() gives file:///C:/... on Windows and percent-encodes characters
    such as # ? % that would otherwise end the path early.
    immutable=1 also stops SQLite creating -wal or -shm files beside it.
    """
    return Path(path).resolve().as_uri() + "?mode=ro&immutable=1"


@contextmanager
def open_read_only(path: Path) -> Iterator[sqlite3.Connection]:
    # A bare `with sqlite3.connect()` only commits; closing matters on
    # Windows, which refuses to delete or move a file that is still open.
    db = sqlite3.connect(read_only_uri(path), uri=True)
    try:
        yield db
    finally:
        db.close()


def summarise(path: Path) -> Summary:
    with open_read_only(path) as db:
        summary = Summary(user_version=db.execute("PRAGMA user_version").fetchone()[0])
        tables = db.execute(
            "SELECT name, coalesce(sql, '') FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        for name, sql in tables:
            virtual = sql.lstrip().upper().startswith("CREATE VIRTUAL TABLE")
            quoted = '"' + name.replace('"', '""') + '"'
            try:
                columns = [r[1] for r in db.execute(f"PRAGMA table_info({quoted})")]
                rows = db.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
            except sqlite3.OperationalError:
                if not virtual:
                    raise
                # Its data still sits in ordinary shadow tables (name_content
                # and so on), which are counted like any other.
                columns, rows = [], None
            summary.tables.append(Table(name, columns, rows, virtual))
    return summary


def schema_sql(path: Path) -> str:
    """The CREATE statements for every table, index, view and trigger."""
    with open_read_only(path) as db:
        statements = [r[0] for r in db.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name")]
    return ";\n\n".join(statements) + ";\n"


def is_sqlite(data: bytes) -> bool:
    return data.startswith(b"SQLite format 3\x00")
