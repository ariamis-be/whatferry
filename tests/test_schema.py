"""Snapshots of WhatsApp's database layout, what changed between two, and filling columns whatferry doesn't know."""

import json
import sqlite3
from contextlib import closing
from datetime import date

import pytest

from conftest import make_sqlite
from test_convert import ACCOUNT, IOS, inputs  # noqa: F401 (fixture)
from whatferry import compat, convert, schema
from whatferry.cli import main

BASE = """
CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, text_data TEXT, status INTEGER DEFAULT 0);
CREATE TABLE chat (_id INTEGER PRIMARY KEY, subject TEXT);
CREATE TABLE stickers (_id INTEGER PRIMARY KEY);
CREATE INDEX message_chat ON message (chat_row_id);
PRAGMA user_version = 1;
"""
USES = {"message": {"_id", "chat_row_id", "text_data"}, "chat": {"_id", "subject"}}


def snap(tmp_path, script, name="db.sqlite"):
    return schema.capture(make_sqlite(tmp_path / name, script))


def changes(tmp_path, after, writes=frozenset({"message", "chat"})):
    old, new = snap(tmp_path, BASE, "old.db"), snap(tmp_path, after, "new.db")
    return {c.what: c.level for c in schema.diff(old, new, USES, set(writes))}


def test_a_snapshot_holds_the_layout_and_nothing_stored(tmp_path):
    s = snap(tmp_path, BASE + "INSERT INTO chat VALUES (1, 'a secret family group');")
    assert s["kind"] == "android" and s["version"] == 1
    assert s["tables"]["message"]["columns"]["status"] == {"type": "INTEGER", "notnull": False, "default": "0",
                                                           "pk": False}
    assert s["indexes"]["message_chat"]["table"] == "message"
    assert "secret" not in json.dumps(s)


def test_the_fingerprint_ignores_which_app_saw_it(tmp_path):
    s = snap(tmp_path, BASE)
    path, new = schema.save(s, "2.26.41.77", tmp_path / "store", date(2026, 10, 25))
    again, new_again = schema.save(snap(tmp_path, BASE, "other.db"), "2.26.42.1", tmp_path / "store", date(2026, 11, 1))
    assert new and not new_again and path == again
    assert [v["app"] for v in json.loads(path.read_text())["seen"]] == ["2.26.41.77", "2.26.42.1"]
    assert schema.fingerprint(json.loads(path.read_text())) == schema.fingerprint(s)


def test_the_same_layout_has_no_changes(tmp_path):
    assert changes(tmp_path, BASE) == {}


def test_what_the_conversion_doesnt_touch_is_harmless(tmp_path):
    found = changes(tmp_path, BASE.replace("CREATE TABLE stickers (_id INTEGER PRIMARY KEY);", "") +
                    "CREATE TABLE reactions (_id INTEGER PRIMARY KEY, x TEXT NOT NULL);")
    assert found == {"table stickers dropped": "harmless", "table reactions added": "harmless"}


def test_a_new_column_on_a_written_table_is_reviewed_and_a_required_one_stops(tmp_path):
    found = changes(tmp_path, BASE.replace("status INTEGER DEFAULT 0", "status INTEGER DEFAULT 0, flags INTEGER, "
                                           "edit_version INTEGER NOT NULL, kind INTEGER NOT NULL DEFAULT 1"))
    assert found["message.flags added (filled like WhatsApp's own rows where they agree)"] == "review"
    assert found["message.kind added (filled like WhatsApp's own rows where they agree)"] == "review"
    assert found["message.edit_version added, NOT NULL with no default"] == "stop"


def test_the_same_column_on_a_table_only_read_is_harmless(tmp_path):
    found = changes(tmp_path, BASE.replace("status INTEGER DEFAULT 0", "status INTEGER DEFAULT 0, edit_version "
                                           "INTEGER NOT NULL"), writes=frozenset())
    assert found == {"message.edit_version added": "harmless"}


def test_a_used_column_gone_stops_an_unused_one_doesnt(tmp_path):
    found = changes(tmp_path, BASE.replace("text_data TEXT, status INTEGER DEFAULT 0", "body TEXT"))
    assert found["message.text_data dropped"] == "stop"
    assert found["message.status dropped"] == "harmless"
    assert found["message.body added (filled like WhatsApp's own rows where they agree)"] == "review"


def test_a_changed_default_is_reviewed(tmp_path):
    assert changes(tmp_path, BASE.replace("DEFAULT 0", "DEFAULT 2")) == {"message.status default '0' -> '2'": "review"}


def test_triggers_and_unique_indexes_on_written_tables_stop(tmp_path):
    found = changes(tmp_path, BASE + "CREATE TRIGGER count_it AFTER INSERT ON message BEGIN SELECT 1; END;"
                    "CREATE UNIQUE INDEX one_subject ON chat (subject); CREATE INDEX by_text ON message (text_data);"
                    "CREATE TRIGGER t2 AFTER INSERT ON stickers BEGIN SELECT 1; END;")
    assert found == {"trigger count_it on message added": "stop", "unique index one_subject on chat added": "stop",
                     "index by_text on message added": "review", "trigger t2 on stickers added": "harmless"}


def test_a_new_database_version_is_reviewed(tmp_path):
    assert changes(tmp_path, BASE.replace("user_version = 1", "user_version = 2")) == {
        "database version 1 -> 2": "review"}


def test_entities_written_must_stay_renumbering_is_fine():
    old = {"tables": {}, "entities": {"WAMessage": 9, "WAChatSession": 4, "WABlackListItem": 1}}
    new = {"tables": {}, "entities": {"WAMessage": 10, "WABlackListItem": 1, "WANewThing": 2}}
    found = {c.what: c.level for c in schema.diff(old, new, {}, {"ZWAMESSAGE"})}
    assert found == {"entity WAChatSession gone": "stop", "entity WANewThing added": "harmless",
                     "entity WAMessage renumbered 9 -> 10": "harmless"}


def test_the_closest_known_layout_is_picked(tmp_path):
    store = tmp_path / "store"
    schema.save(snap(tmp_path, BASE, "a.db"), "1", store)
    schema.save(snap(tmp_path, BASE + "CREATE TABLE extra (_id INTEGER);", "b.db"), "2", store)
    closest, found = schema.closest(snap(tmp_path, BASE + "CREATE TABLE extra (_id INTEGER);", "c.db"), USES,
                                    {"message"}, store)
    assert closest["seen"][0]["app"] == "2" and found == []


def test_the_committed_snapshots_are_the_measured_versions():
    ios, android = schema.known("ios"), schema.known("android")
    assert [s["version"] for s in ios] == ["2.12.14"] and [s["version"] for s in android] == [1]
    assert {"2.26.41.77"} <= {v["app"] for s in android for v in s["seen"]}
    for s in ios + android:
        assert schema.fingerprint(s) == s["fingerprint"]


# compat.py on top of the snapshots

def test_compat_is_tested_on_a_known_layout_and_flags_a_new_one(tmp_path):
    store = tmp_path / "store"
    db = make_sqlite(tmp_path / "ChatStorage.sqlite", IOS)
    schema.save(schema.capture(db), None, store)
    assert compat.check_ios(db, store=store).tested
    with closing(sqlite3.connect(db)) as c:
        c.execute("ALTER TABLE ZWAMESSAGE ADD COLUMN ZEDITVERSION INTEGER")
        c.commit()
    result = compat.check_ios(db, store=store)
    assert result.ok and not result.tested and "ZWAMESSAGE.ZEDITVERSION added" in result.note


def test_a_layout_with_no_snapshot_to_compare_is_flagged(tmp_path):
    db = make_sqlite(tmp_path / "ChatStorage.sqlite", IOS)
    result = compat.check_ios(db, store=tmp_path / "empty")
    assert result.ok and not result.tested and "no record of this database layout" in result.note


def test_a_trigger_on_a_written_table_refuses_the_conversion(inputs):  # noqa: F811
    android, ios, media = inputs
    with closing(sqlite3.connect(ios)) as c:
        c.execute("CREATE TRIGGER wa_count AFTER INSERT ON ZWAMESSAGE BEGIN SELECT 1; END")
        c.commit()
    with pytest.raises(convert.ConvertError, match="trigger wa_count on ZWAMESSAGE added"):
        convert.convert(android, ios, media, ACCOUNT)


# Filling columns whatferry doesn't know

def test_neighbour_values_take_what_whatsapps_rows_agree_on(tmp_path):
    db = sqlite3.connect(make_sqlite(tmp_path / "t.db", "CREATE TABLE t (id INTEGER PRIMARY KEY, a, b, c, known);"))
    db.executemany("INSERT INTO t (a, b, c, known) VALUES (?, ?, ?, ?)",
                   [(7, i % 2, None, 1) for i in range(19)] + [(8, 0, None, 1)])
    assert schema.neighbour_values(db, "t", {"id", "known"}) == {"a": 7}  # 95% agree; b splits; c is empty
    assert schema.neighbour_values(db, "t", {"id", "known"}, share=0.99) == {}
    assert schema.neighbour_values(db, "t", None) == {}  # a table no snapshot has: nothing to compare with
    db.execute("DELETE FROM t WHERE id > 5")
    assert schema.neighbour_values(db, "t", {"id", "known"}) == {}  # too few rows to go by


def test_a_new_column_is_filled_like_whatsapps_own_rows(inputs):  # noqa: F811
    android, ios, media = inputs
    with closing(sqlite3.connect(ios)) as c:
        c.execute("ALTER TABLE ZWAMESSAGE ADD COLUMN ZEDITVERSION INTEGER")
        c.executemany("INSERT INTO ZWAMESSAGE (Z_PK, Z_ENT, ZCHATSESSION, ZMESSAGETYPE, ZSTANZAID, ZMESSAGEDATE) "
                      "VALUES (?, 9, 2, 0, ?, 1)", [(pk, f"b{pk}") for pk in range(2, 14)])
        c.execute("UPDATE ZWAMESSAGE SET ZEDITVERSION = 3")
        c.commit()
    report, run = convert.convert(android, ios, media, ACCOUNT)
    assert report.filled == {"ZWAMESSAGE.ZEDITVERSION": 3}
    with closing(sqlite3.connect(run / "files" / "ChatStorage.sqlite")) as db:
        assert db.execute("SELECT count(*) FROM ZWAMESSAGE WHERE ZEDITVERSION IS NOT 3").fetchone()[0] == 0
    assert any("ZEDITVERSION" in c["what"] for r in report.compatibility for c in r["changes"])


# The command line

def test_cli_check_and_capture(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(schema, "STORE", tmp_path / "store")
    db = make_sqlite(tmp_path / "msgstore.db", BASE)
    assert main(["schema", "check", str(db)]) == 0
    assert "no known layout" in capsys.readouterr().out
    assert main(["schema", "capture", str(db), "--app-version", "2.26.41.77"]) == 0
    assert "New layout" in capsys.readouterr().out
    assert main(["schema", "check", str(db)]) == 0
    out = capsys.readouterr().out
    assert "same as" in out and "seen with 2.26.41.77" in out and "Nothing that matters changed." in out
    with closing(sqlite3.connect(db)) as c:
        c.execute("CREATE TRIGGER t AFTER INSERT ON message BEGIN SELECT 1; END")
        c.commit()
    assert main(["schema", "check", str(db)]) == 1
    out = capsys.readouterr().out
    assert "stop     trigger t on message added" in out and "refuses" in out
    assert main(["schema", "check", str(tmp_path / "missing.db")]) == 1
