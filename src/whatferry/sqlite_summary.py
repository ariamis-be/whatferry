"""Describe a SQLite database by its shape, never by its contents.

A summary holds table names, column lists, row counts and the schema's
CREATE statements: enough to plan a conversion, nothing anyone wrote.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Table:
    name: str
    columns: list[str]
    rows: int


@dataclass
class Summary:
    user_version: int
    tables: list[Table] = field(default_factory=list)

    def table(self, name: str) -> Table | None:
        return next((t for t in self.tables if t.name == name), None)

    def rows(self, name: str) -> int | None:
        t = self.table(name)
        return t.rows if t else None


def open_read_only(path: Path) -> sqlite3.Connection:
    # immutable=1 also stops SQLite creating -wal or -shm files beside it.
    return sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)


def summarise(path: Path) -> Summary:
    with open_read_only(path) as db:
        summary = Summary(user_version=db.execute("PRAGMA user_version").fetchone()[0])
        names = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [r[1] for r in db.execute(f"PRAGMA table_info({quoted})")]
            rows = db.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
            summary.tables.append(Table(name, columns, rows))
    return summary


def schema_sql(path: Path) -> str:
    """The CREATE statements for every table, index, view and trigger."""
    with open_read_only(path) as db:
        statements = [r[0] for r in db.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name")]
    return ";\n\n".join(statements) + ";\n"


def is_sqlite(data: bytes) -> bool:
    return data.startswith(b"SQLite format 3\x00")
