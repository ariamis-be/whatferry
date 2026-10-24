import sqlite3
from contextlib import closing

import pytest

from whatferry import sqlite_summary


def with_app_only_fts(path):
    """A database like WhatsApp's ChatStorage: a full-text table whose tokenizer
    only exists inside the app, so any other SQLite fails to open it."""
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            CREATE TABLE ZWAMESSAGE (Z_PK INTEGER PRIMARY KEY, ZTEXT VARCHAR);
            INSERT INTO ZWAMESSAGE VALUES (1, 'hello'), (2, 'hi');
            CREATE VIRTUAL TABLE ZWAMESSAGE_FTS USING fts4(text, tokenize=simple);
            INSERT INTO ZWAMESSAGE_FTS VALUES ('hello'), ('hi');
        """)
        db.commit()
        db.execute("PRAGMA writable_schema = ON")
        db.execute("UPDATE sqlite_master SET sql = replace(sql, 'tokenize=simple', 'tokenize=wa_tokenizer') "
                   "WHERE name = 'ZWAMESSAGE_FTS'")
        db.commit()
    return path


def test_virtual_table_with_an_unknown_module_is_listed_not_fatal(tmp_path):
    path = with_app_only_fts(tmp_path / "ChatStorage.sqlite")
    with closing(sqlite3.connect(path)) as db, pytest.raises(sqlite3.OperationalError, match="wa_tokenizer"):
        db.execute('PRAGMA table_info("ZWAMESSAGE_FTS")').fetchall()

    summary = sqlite_summary.summarise(path)
    fts = summary.table("ZWAMESSAGE_FTS")
    assert fts.virtual and fts.rows is None and fts.columns == []
    assert summary.rows("ZWAMESSAGE") == 2
    # The shadow tables holding its data are ordinary and still counted.
    assert summary.rows("ZWAMESSAGE_FTS_content") == 2
    assert "wa_tokenizer" in sqlite_summary.schema_sql(path)


def test_other_errors_still_surface(tmp_path, monkeypatch):
    path = tmp_path / "x.sqlite"
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE t (a)")
        db.commit()
    monkeypatch.setattr(sqlite_summary, "open_read_only", lambda p: _Broken())
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        sqlite_summary.summarise(path)


class _Broken:
    """A connection whose ordinary table can't be read: not a virtual table, so it must raise."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, *args):
        if sql.startswith("PRAGMA user_version"):
            return _Rows([(0,)])
        if sql.startswith("SELECT name"):
            return _Rows([("t", "CREATE TABLE t (a)")])
        raise sqlite3.OperationalError("disk I/O error")


class _Rows(list):
    def fetchone(self):
        return self[0]

    def fetchall(self):
        return list(self)
