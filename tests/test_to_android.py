"""iPhone -> Android: converting, writing the crypt15 backup, and copying it onto the phone."""

import json
import sqlite3
import stat
import sys
from contextlib import closing
from pathlib import Path

import pytest
from wa_crypt_tools.lib.key.keyfactory import KeyFactory

from conftest import make_sqlite
from test_android import KEY, OTHER_KEY, encrypt
from test_convert import ANDROID, IOS
from whatferry import adb, android, android_writer, compat, convert, to_android
from whatferry.android_writer import AndroidWriteError

T0 = 1_700_000_000_000

# The tables a conversion writes, as WhatsApp for Android 2.26.41 defines them
# (from a real msgstore.db), with the account's own jid and nothing else.
TEMPLATE = """
PRAGMA user_version = 1;
CREATE TABLE jid(_id INTEGER PRIMARY KEY AUTOINCREMENT,user TEXT NOT NULL,server TEXT NOT NULL,agent INTEGER,
  device INTEGER,type INTEGER,raw_string TEXT);
CREATE TABLE jid_map(lid_row_id INTEGER PRIMARY KEY NOT NULL,jid_row_id INTEGER NOT NULL, sort_id INTEGER);
CREATE TABLE chat(_id INTEGER PRIMARY KEY AUTOINCREMENT,jid_row_id INTEGER UNIQUE,hidden INTEGER,subject TEXT,
  created_timestamp INTEGER,display_message_row_id INTEGER,last_message_row_id INTEGER,last_read_message_row_id INTEGER,
  last_read_receipt_sent_message_row_id INTEGER,last_important_message_row_id INTEGER,archived INTEGER,
  sort_timestamp INTEGER,mod_tag INTEGER,gen REAL,spam_detection INTEGER,unseen_earliest_message_received_time INTEGER,
  unseen_message_count INTEGER,unseen_missed_calls_count INTEGER,unseen_row_count INTEGER,plaintext_disabled INTEGER,
  vcard_ui_dismissed INTEGER,change_number_notified_message_row_id INTEGER,show_group_description INTEGER,
  ephemeral_expiration INTEGER,last_read_ephemeral_message_row_id INTEGER,ephemeral_setting_timestamp INTEGER,
  ephemeral_displayed_exemptions INTEGER,ephemeral_disappearing_messages_initiator INTEGER,
  unseen_important_message_count INTEGER NOT NULL DEFAULT 0,group_type INTEGER NOT NULL DEFAULT 0,
  last_message_reaction_row_id INTEGER,last_seen_message_reaction_row_id INTEGER,unseen_message_reaction_count INTEGER,
  unseen_comment_message_count INTEGER,growth_lock_level INTEGER,growth_lock_expiration_ts INTEGER,
  last_read_message_sort_id INTEGER,display_message_sort_id INTEGER,last_message_sort_id INTEGER,
  last_read_receipt_sent_message_sort_id INTEGER,has_new_community_admin_dialog_been_acknowledged INTEGER NOT NULL
  DEFAULT 0,history_sync_progress INTEGER,chat_lock INTEGER,chat_origin TEXT,participation_status INTEGER,
  account_jid_row_id INTEGER);
CREATE TABLE message(_id INTEGER PRIMARY KEY AUTOINCREMENT,chat_row_id INTEGER NOT NULL,from_me INTEGER NOT NULL,
  key_id TEXT NOT NULL,sender_jid_row_id INTEGER,status INTEGER,broadcast INTEGER,recipient_count INTEGER,
  participant_hash TEXT,origination_flags INTEGER,origin INTEGER,timestamp INTEGER,received_timestamp INTEGER,
  receipt_server_timestamp INTEGER,message_type INTEGER,text_data TEXT,starred INTEGER,lookup_tables INTEGER,
  message_add_on_flags INTEGER,view_mode INTEGER,sort_id INTEGER NOT NULL DEFAULT 0, translated_text TEXT,
  view_replies_thread_id INTEGER, server_sts INTEGER);
CREATE TABLE message_media(message_row_id INTEGER PRIMARY KEY,chat_row_id INTEGER,autotransfer_retry_enabled INTEGER,
  multicast_id TEXT,media_job_uuid TEXT,transferred INTEGER,transcoded INTEGER,file_path TEXT,file_size INTEGER,
  suspicious_content INTEGER,trim_from INTEGER,trim_to INTEGER,face_x INTEGER,face_y INTEGER,media_key BLOB,
  media_key_timestamp INTEGER,width INTEGER,height INTEGER,has_streaming_sidecar INTEGER,gif_attribution INTEGER,
  thumbnail_height_width_ratio REAL,direct_path TEXT,first_scan_sidecar BLOB,first_scan_length INTEGER,
  message_url TEXT,mime_type TEXT,file_length INTEGER,media_name TEXT,file_hash TEXT,media_duration INTEGER,
  page_count INTEGER,enc_file_hash TEXT,partial_media_hash TEXT,partial_media_enc_hash TEXT,
  is_animated_sticker INTEGER,original_file_hash TEXT,mute_video INTEGER DEFAULT 0,media_caption TEXT);
CREATE TABLE message_location(message_row_id INTEGER PRIMARY KEY,chat_row_id INTEGER,latitude REAL,longitude REAL,
  place_name TEXT,place_address TEXT,url TEXT,live_location_share_duration INTEGER,live_location_sequence_number INTEGER,
  live_location_final_latitude REAL,live_location_final_longitude REAL,live_location_final_timestamp INTEGER,
  map_download_status INTEGER);
CREATE TABLE message_vcard(_id INTEGER PRIMARY KEY AUTOINCREMENT,message_row_id INTEGER,vcard TEXT);
CREATE TABLE group_participant_user(_id INTEGER PRIMARY KEY AUTOINCREMENT,group_jid_row_id INTEGER NOT NULL,
  user_jid_row_id INTEGER NOT NULL,rank INTEGER,pending INTEGER,add_timestamp INTEGER, label TEXT,
  join_method INTEGER, group_history_send_state INTEGER);
CREATE TABLE props (_id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, value TEXT);
INSERT INTO props (key, value) VALUES ('user_push_name', 'Me');
INSERT INTO jid (user, server, agent, device, type, raw_string) VALUES ('32470000999', 's.whatsapp.net', 0, 0, 0,
  '32470000999@s.whatsapp.net');
"""


@pytest.fixture
def iphone(tmp_path, private_home):
    """An iPhone account holding the Android fixture's history (made by the forward converter), and its media."""
    media = tmp_path / "android-media"
    for rel, data in (("WhatsApp Images/Sent/IMG-1.jpg", b"\xff\xd8 a jpeg"), ("WhatsApp Video/VID-1.mp4", b"mp4"),
                      ("WhatsApp Voice Notes/PTT-1.opus", b"OggS voice")):
        (media / rel).parent.mkdir(parents=True, exist_ok=True)
        (media / rel).write_bytes(data)
    report, run = convert.convert(make_sqlite(tmp_path / "msgstore-src.db", ANDROID),
                                  make_sqlite(tmp_path / "chat.sqlite", IOS), media)
    files = run / "files" / "Message"

    def read(local):
        path = files / local
        return path.read_bytes() if path.is_file() else None

    return run / "files" / "ChatStorage.sqlite", read


def rows(db_path, sql, params=()):
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(sql, params).fetchall()


def test_round_trip_reproduces_the_android_history(iphone, tmp_path):
    ios_db, media = iphone
    template = make_sqlite(tmp_path / "template.db", TEMPLATE)
    report, run = to_android.convert(ios_db, template, media)
    merged = run / "files" / "msgstore.db"

    # Every message the forward converter carried comes back with its id, kind and text.
    original = set(rows(tmp_path / "msgstore-src.db",
                        "SELECT key_id, from_me, message_type, coalesce(text_data, '') FROM message "
                        "WHERE message_type IN (0, 1, 2, 3, 4, 5, 15) AND chat_row_id != 14"))
    back = set(rows(merged, "SELECT key_id, from_me, message_type, coalesce(text_data, '') FROM message"))
    assert original == back
    # The contact (one chat on the iPhone for its number and privacy id) and the group.
    assert report.chats_created == 2 and report.groups_created == 1
    assert report.media_files_copied == 3 and report.media_files_missing == 0
    assert not any(v for k, v in report.checks.items() if k not in ("integrity", "messages", "chats",
                                                                  "first message", "last message"))
    assert report.checks["integrity"] == "ok"

    # Rows as WhatsApp for Android writes them.
    sent = rows(merged, "SELECT status, received_timestamp, sender_jid_row_id, receipt_server_timestamp FROM message "
                        "WHERE key_id = 'k-out'")[0]
    assert sent == (13, 0, 0, -1)
    received = rows(merged, "SELECT status, received_timestamp = timestamp FROM message WHERE key_id = 'k-in'")[0]
    assert received == (0, 1)
    member = rows(merged, "SELECT j.user, j.server FROM message m JOIN jid j ON j._id = m.sender_jid_row_id "
                          "WHERE m.key_id = 'k-g1'")[0]
    assert member == ("888222", "lid")
    chat = rows(merged, "SELECT c.hidden, c.plaintext_disabled, c.chat_origin, c.last_message_row_id = m._id, "
                        "c.sort_timestamp = m.timestamp, c.last_message_sort_id = m.sort_id FROM chat c "
                        "JOIN message m ON m._id = (SELECT _id FROM message WHERE chat_row_id = c._id "
                        "ORDER BY sort_id DESC LIMIT 1)")
    assert chat and all(r == (0, 1, "general", 1, 1, 1) for r in chat)
    assert rows(merged, "SELECT latitude, longitude, place_name FROM message_location") == [(50.85, 4.35, "Brussels")]
    assert rows(merged, "SELECT vcard FROM message_vcard") == [("BEGIN:VCARD\nFN:Bob\nEND:VCARD",)]
    assert rows(merged, "SELECT count(*) FROM group_participant_user")[0][0] >= 1

    # Media files where WhatsApp for Android keeps them, named its way.
    paths = {p for (p,) in rows(merged, "SELECT file_path FROM message_media WHERE file_path IS NOT NULL")}
    assert any(p.startswith("Media/WhatsApp Images/Sent/IMG-20231114-WF0001") for p in paths), paths
    assert any(p.startswith("Media/WhatsApp Voice Notes/202346/PTT-20231114-WF0001.opus") for p in paths), paths
    for p in paths:
        assert (run / "files" / p).is_file()
    hashed = rows(merged, "SELECT file_hash, file_size FROM message_media WHERE file_path LIKE '%IMG-%'")[0]
    assert len(hashed[0]) == 44 and hashed[1] == len(b"\xff\xd8 a jpeg")


def test_existing_messages_are_recognised_and_history_sorts_before_them(iphone, tmp_path):
    """The Android account already has the contact's chat (under its privacy id) with a newer message."""
    ios_db, media = iphone
    template = make_sqlite(tmp_path / "template.db", TEMPLATE + f"""
        INSERT INTO jid (_id, user, server, type, raw_string) VALUES (50, '32470000111', 's.whatsapp.net', 0, NULL),
                                                                    (51, '999111', 'lid', 18, NULL);
        INSERT INTO jid_map VALUES (51, 50, 1);
        INSERT INTO chat (_id, jid_row_id, hidden) VALUES (60, 51, 0);
        INSERT INTO message (_id, chat_row_id, from_me, key_id, timestamp, message_type, text_data, sort_id)
          VALUES (70, 60, 1, 'k-out', {T0 + 2000}, 0, 'hi', 70), (71, 60, 0, 'later', {T0 + 99999}, 0, 'new', 71);
    """)
    report, run = to_android.convert(ios_db, template, media)
    merged = run / "files" / "msgstore.db"
    assert report.chats_matched == 1 and report.already_there == 1
    ordered = [k for (k,) in rows(merged, "SELECT key_id FROM message WHERE chat_row_id = 60 ORDER BY sort_id")]
    assert ordered[-1] == "later" and ordered.index("k-in") < ordered.index("k-out")
    assert report.checks["duplicate sort ids"] == 0 and report.checks["sort out of time order"] == 0


def test_a_database_missing_a_column_is_refused(iphone, tmp_path):
    ios_db, media = iphone
    template = make_sqlite(tmp_path / "template.db", TEMPLATE.replace("received_timestamp INTEGER,", ""))
    with pytest.raises(convert.ConvertError, match="message.received_timestamp"):
        to_android.convert(ios_db, template, media)


def test_untested_versions_convert_with_a_note(tmp_path):
    db = make_sqlite(tmp_path / "t.db", TEMPLATE.replace("PRAGMA user_version = 1", "PRAGMA user_version = 7"))
    result = compat.check_android(db, "2.27.1.1", compat.ANDROID_WRITE)
    assert result.ok and not result.tested and "2.27.1.1" in result.note


# Writing the crypt15 backup

@pytest.fixture
def converted(iphone, tmp_path):
    ios_db, media = iphone
    template = make_sqlite(tmp_path / "template.db", TEMPLATE)
    reference = encrypt(template, tmp_path / "msgstore.db.crypt15")
    _, run = to_android.convert(ios_db, template, media)
    return reference, run


def test_writes_a_backup_that_decrypts_to_the_conversion(converted):
    reference, run = converted
    key = KeyFactory.from_hex(KEY)
    report, folder = android_writer.write_backup(reference, key, run)
    plain, header = android.decrypt(folder / "Databases" / "msgstore.db.crypt15", key)
    assert plain == (run / "files" / "msgstore.db").read_bytes()
    assert header.app_version == "2.26.20.10" and header.number_ends_with == "42"  # the original's header
    assert report.verified and report.media_files == 3
    assert {p.relative_to(folder).parts[0] for p in folder.rglob("*") if p.is_file()} == {"Databases", "Media"}
    # A fresh IV: never the original's nonce under the same key.
    written = (folder / "Databases" / "msgstore.db.crypt15").read_bytes()
    assert written[:80] != reference.read_bytes()[:80]


def test_writer_refuses_another_backup_unless_told(converted, tmp_path):
    reference, run = converted
    key = KeyFactory.from_hex(KEY)
    other = encrypt(make_sqlite(tmp_path / "other.db", TEMPLATE + "INSERT INTO props (key) VALUES ('x');"),
                    tmp_path / "other.crypt15")
    with pytest.raises(AndroidWriteError, match="isn't the one the conversion was made from"):
        android_writer.write_backup(other, key, run)
    report, _ = android_writer.write_backup(other, key, run, check_source=False)
    assert not report.source_checked
    with pytest.raises(android.DecryptError):
        android_writer.write_backup(reference, KeyFactory.from_hex(OTHER_KEY), run)


def test_writer_refuses_a_forward_conversion(converted, tmp_path):
    reference, run = converted
    report = json.loads((run / "report.json").read_text())
    (run / "report.json").unlink()
    (run / "report.json").write_text(json.dumps(report | {"direction": None}))
    with pytest.raises(AndroidWriteError, match="Android -> iPhone"):
        android_writer.write_backup(reference, KeyFactory.from_hex(KEY), run)


def test_command_line_convert_and_write(iphone, tmp_path, monkeypatch, capsys):
    from whatferry.cli import main

    ios_db, _ = iphone
    template = make_sqlite(tmp_path / "template.db", TEMPLATE)
    reference = encrypt(template, tmp_path / "msgstore.db.crypt15")
    assert main(["android", "convert", str(ios_db), str(template)]) == 0
    out = capsys.readouterr().out
    assert "iPhone messages" in out and "no problems" in out
    run = Path(out.split("report.json are in ", 1)[1].split(" (readable only by you)", 1)[0])
    monkeypatch.setenv("WHATFERRY_ANDROID_KEY", KEY)
    assert main(["android", "write", str(reference), str(run)]) == 0
    assert "decrypted again and verified" in capsys.readouterr().out


# Copying onto the phone, with a fake adb that keeps the phone's files in a folder.

FAKE_PHONE_ADB = """\
#!{python}
import os, shutil, subprocess, sys
root = os.environ["FAKE_PHONE"]
local = lambda p: p.replace("/sdcard", root)
args = sys.argv[1:]
if args == ["version"]:
    print("Android Debug Bridge version 1.0.41")
elif args == ["devices", "-l"]:
    print("List of devices attached")
    print("PHONE1 device usb:1 model:Pixel_8_Pro transport_id:1")
elif args[:3] == ["-s", "PHONE1", "shell"] and "stat -c" in args[3]:
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.startswith("msgstore") and "/Databases" in dirpath:
                path = os.path.join(dirpath, f)
                print(f"{{os.path.getsize(path)}}|0|{{path.replace(root, '/sdcard')}}")
elif args[:3] == ["-s", "PHONE1", "shell"]:
    sys.exit(subprocess.run(["sh", "-c", local(args[3])]).returncode)
elif args[:3] == ["-s", "PHONE1", "push"]:
    src, dest = args[3], local(args[4])
    if os.environ.get("FAKE_PUSH_FAILS") and os.environ["FAKE_PUSH_FAILS"] in args[4]:
        print("adb: error: device disconnected", file=sys.stderr)
        sys.exit(1)
    if os.path.isdir(src):
        shutil.copytree(src, dest)
    else:
        shutil.copy(src, dest)
else:
    print("unexpected", args, file=sys.stderr)
    sys.exit(1)
"""


@pytest.fixture
def phone(tmp_path, monkeypatch):
    root = tmp_path / "phone"
    whatsapp = root / "Android/media/com.whatsapp/WhatsApp"
    (whatsapp / "Databases").mkdir(parents=True)
    (whatsapp / "Databases" / "msgstore.db.crypt15").write_bytes(b"the phone's own backup")
    (whatsapp / "Media/WhatsApp Images").mkdir(parents=True)
    tool = tmp_path / "bin" / "adb"
    tool.parent.mkdir()
    tool.write_text(FAKE_PHONE_ADB.format(python=sys.executable))
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_PHONE", str(root))
    return tool, whatsapp


@pytest.mark.skipif(sys.platform == "win32", reason="the fake adb is a script with a shebang")
def test_push_keeps_whats_on_the_phone(phone, converted):
    tool, whatsapp = phone
    reference, run = converted
    _, folder = android_writer.write_backup(reference, KeyFactory.from_hex(KEY), run)
    result = adb.push(tool, "PHONE1", adb.WHATSAPP_ROOT, folder)
    assert (whatsapp / "Databases" / "msgstore.db.crypt15").read_bytes() == \
        (folder / "Databases" / "msgstore.db.crypt15").read_bytes()
    kept = Path(result["kept"].replace("/sdcard", str(whatsapp.parents[3])))
    assert kept.read_bytes() == b"the phone's own backup"
    for path in (p for p in (folder / "Media").rglob("*") if p.is_file()):
        assert (whatsapp / "Media" / path.relative_to(folder / "Media")).read_bytes() == path.read_bytes()
    assert result["media_files"] == 3
    assert not list(whatsapp.glob(".whatferry-*")), "the staging folder is removed"


@pytest.mark.skipif(sys.platform == "win32", reason="the fake adb is a script with a shebang")
def test_push_changes_nothing_when_a_name_is_taken(phone, converted):
    tool, whatsapp = phone
    reference, run = converted
    _, folder = android_writer.write_backup(reference, KeyFactory.from_hex(KEY), run)
    clash = next(p for p in (folder / "Media").rglob("*") if p.is_file()).relative_to(folder / "Media")
    (whatsapp / "Media" / clash).parent.mkdir(parents=True, exist_ok=True)
    (whatsapp / "Media" / clash).write_bytes(b"the phone's own photo")
    before = {p: p.read_bytes() for p in whatsapp.rglob("*") if p.is_file()}
    with pytest.raises(adb.AdbError, match=r"already has 1 file\(s\) .*\(such as WhatsApp [^)]+\); nothing was changed"):
        adb.push(tool, "PHONE1", adb.WHATSAPP_ROOT, folder)
    assert {p: p.read_bytes() for p in whatsapp.rglob("*") if p.is_file()} == before


@pytest.mark.skipif(sys.platform == "win32", reason="the fake adb is a script with a shebang")
def test_a_failed_backup_copy_puts_the_phones_own_back(phone, converted, monkeypatch):
    tool, whatsapp = phone
    reference, run = converted
    _, folder = android_writer.write_backup(reference, KeyFactory.from_hex(KEY), run)
    monkeypatch.setenv("FAKE_PUSH_FAILS", "msgstore.db.crypt15")
    with pytest.raises(adb.AdbError, match="device disconnected.*back in place"):
        adb.push(tool, "PHONE1", adb.WHATSAPP_ROOT, folder)
    assert (whatsapp / "Databases" / "msgstore.db.crypt15").read_bytes() == b"the phone's own backup"
    assert [p.name for p in (whatsapp / "Databases").iterdir()] == ["msgstore.db.crypt15"]
    assert not list(whatsapp.glob(".whatferry-*")), "the staging folder is removed"


@pytest.mark.skipif(sys.platform == "win32", reason="the fake adb is a script with a shebang")
def test_a_failed_media_copy_changes_nothing(phone, converted, monkeypatch):
    tool, whatsapp = phone
    reference, run = converted
    _, folder = android_writer.write_backup(reference, KeyFactory.from_hex(KEY), run)
    before = {p: p.read_bytes() for p in whatsapp.rglob("*") if p.is_file()}
    monkeypatch.setenv("FAKE_PUSH_FAILS", ".whatferry-")
    with pytest.raises(adb.AdbError, match="device disconnected"):
        adb.push(tool, "PHONE1", adb.WHATSAPP_ROOT, folder)
    assert {p: p.read_bytes() for p in whatsapp.rglob("*") if p.is_file()} == before
    assert not list(whatsapp.glob(".whatferry-*"))


@pytest.mark.skipif(sys.platform == "win32", reason="the fake adb is a script with a shebang")
def test_push_only_into_whatsapp_folders(phone, converted, tmp_path):
    tool, _ = phone
    with pytest.raises(adb.AdbError, match="isn't one of the phone's WhatsApp folders"):
        adb.push(tool, "PHONE1", "/sdcard/DCIM", tmp_path)
