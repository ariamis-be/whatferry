"""Android history into an iPhone account's ChatStorage, on small faithful databases."""

import base64
import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from conftest import make_sqlite
from whatferry import convert
from whatferry.cli import main

APPLE = convert.APPLE_EPOCH
T0 = 1_700_000_000_000  # Android timestamps are milliseconds

ANDROID = f"""
CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, raw_string TEXT);
CREATE TABLE jid_map (lid_row_id INTEGER, jid_row_id INTEGER, sort_id INTEGER);
CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT, archived INTEGER, created_timestamp INTEGER);
CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER, key_id TEXT, sender_jid_row_id INTEGER,
                      timestamp INTEGER, message_type INTEGER, text_data TEXT, starred INTEGER);
CREATE TABLE message_media (message_row_id INTEGER PRIMARY KEY, file_path TEXT, file_size INTEGER, media_duration INTEGER,
                            width INTEGER, height INTEGER, media_name TEXT, media_caption TEXT);
CREATE TABLE message_location (message_row_id INTEGER PRIMARY KEY, latitude REAL, longitude REAL, place_name TEXT);
CREATE TABLE message_vcard (_id INTEGER PRIMARY KEY, message_row_id INTEGER, vcard TEXT);
CREATE TABLE message_quoted (message_row_id INTEGER PRIMARY KEY);
CREATE TABLE message_add_on (_id INTEGER PRIMARY KEY);
CREATE TABLE props (key TEXT, value TEXT);
INSERT INTO props VALUES ('user_push_name', 'Me');
INSERT INTO jid VALUES (2, '32470000111', 's.whatsapp.net', '32470000111@s.whatsapp.net'),
                       (3, '999111', 'lid', '999111@lid'),
                       (4, '120363000', 'g.us', '120363000@g.us'),
                       (5, '32470000222', 's.whatsapp.net', '32470000222@s.whatsapp.net'),
                       (6, '888222', 'lid', '888222@lid'),
                       (7, 'status', 'broadcast', 'status@broadcast'),
                       (8, '32470000333', 's.whatsapp.net', '32470000333@s.whatsapp.net'),
                       (9, '32470000444', 's.whatsapp.net', '32470000444@s.whatsapp.net');
INSERT INTO jid_map VALUES (3, 2, 1), (6, 5, 2);
-- One contact twice (phone and privacy id), a group, a chat of only system
-- notices, and the status broadcast.
INSERT INTO chat VALUES (10, 2, NULL, 0, {T0}), (11, 3, NULL, 1, {T0}), (12, 4, 'Family', 0, {T0}),
                        (13, 9, NULL, 0, {T0}), (14, 7, NULL, 0, {T0});
INSERT INTO message VALUES
  (1, 10, 0, 'k-in', 0, {T0 + 1000}, 0, 'hello', 0),
  (2, 10, 1, 'k-out', 0, {T0 + 2000}, 0, 'hi', 1),
  (3, 11, 1, 'k-img', 0, {T0 + 3000}, 1, 'a caption', 0),
  (4, 11, 0, 'k-vid', 0, {T0 + 4000}, 3, NULL, 0),
  (5, 12, 0, 'k-g1', 6, {T0 + 5000}, 0, 'from a member', 0),
  (6, 12, 0, 'k-g2', 8, {T0 + 6000}, 0, 'from a past member', 0),
  (7, 12, 1, 'k-g3', 0, {T0 + 7000}, 5, NULL, 0),
  (8, 12, 0, 'k-g4', 6, {T0 + 8000}, 4, 'Bob', 0),
  (9, 12, 0, 'k-g5', 6, {T0 + 9000}, 15, NULL, 0),
  (10, 12, 0, 'k-sys', 0, {T0 + 9500}, 7, NULL, 0),
  (11, 13, 0, 'k-only-sys', 0, {T0 + 9600}, 7, NULL, 0),
  (12, 14, 0, 'k-status', 2, {T0 + 9700}, 0, 'a status', 0),
  (13, 10, 0, 'k-poll', 0, {T0 + 9800}, 99, NULL, 0),
  (14, 10, 0, 'k-voice', 0, {T0 + 9900}, 2, NULL, 0);
INSERT INTO message_media VALUES
  (3, 'Media/WhatsApp Images/Sent/IMG-1.jpg', 1234, NULL, 2048, 1536, NULL, NULL),
  (4, 'Media/WhatsApp Video/VID-1.mp4', 9999, 12, 640, 480, NULL, NULL),
  (14, 'Media/WhatsApp Voice Notes/PTT-1.opus', 777, 5, NULL, NULL, NULL, NULL);
INSERT INTO message_location VALUES (7, 50.85, 4.35, 'Brussels');
INSERT INTO message_vcard VALUES (1, 8, 'BEGIN:VCARD\nFN:Bob\nEND:VCARD');
INSERT INTO message_quoted VALUES (5);
INSERT INTO message_add_on VALUES (1), (2);
"""

IOS = f"""
CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER PRIMARY KEY, Z_NAME VARCHAR, Z_SUPER INTEGER, Z_MAX INTEGER);
INSERT INTO Z_PRIMARYKEY VALUES (4, 'WAChatSession', 0, 2), (5, 'WAGroupInfo', 0, 1), (6, 'WAGroupMember', 0, 1),
                                (8, 'WAMediaItem', 0, 0), (9, 'WAMessage', 0, 1);
CREATE TABLE ZWACHATSESSION (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, Z_OPT INTEGER, ZARCHIVED INTEGER, ZCONTACTABID INTEGER,
  ZFLAGS INTEGER, ZHIDDEN INTEGER, ZIDENTITYVERIFICATIONEPOCH INTEGER, ZIDENTITYVERIFICATIONSTATE INTEGER,
  ZMESSAGECOUNTER INTEGER, ZREMOVED INTEGER, ZSESSIONTYPE INTEGER, ZSPOTLIGHTSTATUS INTEGER, ZUNREADCOUNT INTEGER,
  ZGROUPINFO INTEGER, ZLASTMESSAGE INTEGER, ZPROPERTIES INTEGER, ZLASTMESSAGEDATE TIMESTAMP,
  ZLOCATIONSHARINGENDDATE TIMESTAMP, ZCONTACTIDENTIFIER VARCHAR, ZCONTACTJID VARCHAR, ZETAG VARCHAR,
  ZLASTMESSAGETEXT VARCHAR, ZPARTNERNAME VARCHAR, ZSAVEDINPUT VARCHAR);
CREATE TABLE ZWAMESSAGE (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, Z_OPT INTEGER, ZCHILDMESSAGESDELIVEREDCOUNT INTEGER,
  ZCHILDMESSAGESPLAYEDCOUNT INTEGER, ZCHILDMESSAGESREADCOUNT INTEGER, ZDATAITEMVERSION INTEGER, ZDOCID INTEGER,
  ZENCRETRYCOUNT INTEGER, ZFILTEREDRECIPIENTCOUNT INTEGER, ZFLAGS INTEGER, ZGROUPEVENTTYPE INTEGER, ZISFROMME INTEGER,
  ZMESSAGEERRORSTATUS INTEGER, ZMESSAGESTATUS INTEGER, ZMESSAGETYPE INTEGER, ZSORT INTEGER, ZSPOTLIGHTSTATUS INTEGER,
  ZSTARRED INTEGER, ZCHATSESSION INTEGER, ZGROUPMEMBER INTEGER, ZLASTSESSION INTEGER, ZMEDIAITEM INTEGER,
  ZMESSAGEINFO INTEGER, ZPARENTMESSAGE INTEGER, ZMESSAGEDATE TIMESTAMP, ZSENTDATE TIMESTAMP, ZFROMJID VARCHAR,
  ZMEDIASECTIONID VARCHAR, ZPHASH VARCHAR, ZPUSHNAME VARCHAR, ZSTANZAID VARCHAR, ZTEXT VARCHAR, ZTOJID VARCHAR);
CREATE TABLE ZWAMEDIAITEM (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, Z_OPT INTEGER, ZCLOUDSTATUS INTEGER, ZFILESIZE INTEGER,
  ZMEDIAORIGIN INTEGER, ZMOVIEDURATION INTEGER, ZMESSAGE INTEGER, ZASPECTRATIO FLOAT, ZHACCURACY FLOAT, ZLATITUDE FLOAT,
  ZLONGITUDE FLOAT, ZMEDIAURLDATE TIMESTAMP, ZAUTHORNAME VARCHAR, ZCOLLECTIONNAME VARCHAR, ZMEDIALOCALPATH VARCHAR,
  ZMEDIAURL VARCHAR, ZTHUMBNAILLOCALPATH VARCHAR, ZTITLE VARCHAR, ZVCARDNAME VARCHAR, ZVCARDSTRING VARCHAR,
  ZXMPPTHUMBPATH VARCHAR, ZMEDIAKEY BLOB, ZMETADATA BLOB);
CREATE TABLE ZWAGROUPINFO (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, Z_OPT INTEGER, ZSTATE INTEGER, ZCHATSESSION INTEGER,
  ZLASTMESSAGEOWNER INTEGER, ZCREATIONDATE TIMESTAMP, ZSUBJECTTIMESTAMP TIMESTAMP, ZCREATORJID VARCHAR, ZOWNERJID VARCHAR,
  ZPICTUREID VARCHAR, ZPICTUREPATH VARCHAR, ZSOURCEJID VARCHAR, ZSUBJECTOWNERJID VARCHAR);
CREATE TABLE ZWAGROUPMEMBER (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, Z_OPT INTEGER, ZCONTACTABID INTEGER, ZISACTIVE INTEGER,
  ZISADMIN INTEGER, ZSENDERKEYSENT INTEGER, ZCHATSESSION INTEGER, ZRECENTGROUPCHAT INTEGER, ZCONTACTIDENTIFIER VARCHAR,
  ZCONTACTNAME VARCHAR, ZFIRSTNAME VARCHAR, ZMEMBERJID VARCHAR);
-- The new account already holds the group (synced, with a member known by
-- privacy id and one system notice newer than the history) and a broadcast.
INSERT INTO ZWACHATSESSION (Z_PK, Z_ENT, ZSESSIONTYPE, ZCONTACTJID, ZPARTNERNAME, ZGROUPINFO, ZMESSAGECOUNTER)
  VALUES (1, 4, 1, '120363000@g.us', 'Family', 1, 1), (2, 4, 2, 'status@broadcast', 'Status', NULL, 0);
INSERT INTO ZWAGROUPINFO (Z_PK, Z_ENT, ZCHATSESSION) VALUES (1, 5, 1);
INSERT INTO ZWAGROUPMEMBER (Z_PK, Z_ENT, ZISACTIVE, ZCHATSESSION, ZMEMBERJID, ZCONTACTNAME)
  VALUES (1, 6, 1, 1, '888222@lid', 'Bob');
INSERT INTO ZWAMESSAGE (Z_PK, Z_ENT, ZCHATSESSION, ZMESSAGETYPE, ZISFROMME, ZSTANZAID, ZMESSAGEDATE, ZSORT)
  VALUES (1, 9, 1, 6, 0, 'sys1', {T0 / 1000 - APPLE + 100000}, 1);
"""

ACCOUNT = "data/0A1B2C3D-4E5F-4A6B-8C7D-9E0F1A2B3C4D"


@pytest.fixture
def inputs(tmp_path):
    android = make_sqlite(tmp_path / "msgstore.db", ANDROID)
    ios = make_sqlite(tmp_path / "ChatStorage.sqlite", IOS)
    media = tmp_path / "media"
    (media / "WhatsApp Images" / "Sent").mkdir(parents=True)
    (media / "WhatsApp Images" / "Sent" / "IMG-1.jpg").write_bytes(b"\xff\xd8 a jpeg")
    (media / "WhatsApp Voice Notes").mkdir()
    (media / "WhatsApp Voice Notes" / "PTT-1.opus").write_bytes(b"OggS voice")
    return android, ios, media


@pytest.fixture
def converted(inputs):
    android, ios, media = inputs
    report, run = convert.convert(android, ios, media, ACCOUNT)
    db = sqlite3.connect(run / "files" / "ChatStorage.sqlite")
    db.row_factory = sqlite3.Row
    yield report, run, db
    db.close()


def one(db, sql, *args):
    return db.execute(sql, args).fetchone()


def test_counts_and_checks(converted):
    report, _, _ = converted
    assert report.android_messages == 14
    # iPhone types: 0 text, 1 image, 2 video, 3 audio, 4 contact, 5 location, 14 deleted
    assert report.converted == {"0": 4, "1": 1, "2": 1, "3": 1, "4": 1, "5": 1, "14": 1}
    assert report.skipped == {"7": 2, "99": 1, "0": 1}  # system notices, a poll, the status post
    assert (report.chats_matched, report.chats_created, report.members_created) == (1, 1, 1)
    assert report.not_converted_yet == {"quoted replies": 1, "reactions and other add-ons": 2}
    assert report.checks["integrity"] == "ok"
    for key in ("messages without a chat", "media rows not pointing back", "group messages without a member",
                "duplicate message ids in a chat", "sort out of date order", "primary keys behind rows"):
        assert report.checks[key] == 0, key


def test_a_contact_known_by_phone_and_privacy_id_becomes_one_chat(converted):
    _, _, db = converted
    sessions = db.execute("SELECT ZCONTACTJID, ZPARTNERNAME, ZSESSIONTYPE FROM ZWACHATSESSION ORDER BY Z_PK").fetchall()
    assert [tuple(s) for s in sessions] == [
        ("120363000@g.us", "Family", 1), ("status@broadcast", "Status", 2), ("32470000111@s.whatsapp.net", "+32470000111", 0)]
    pk = one(db, "SELECT Z_PK FROM ZWACHATSESSION WHERE ZCONTACTJID = '32470000111@s.whatsapp.net'")[0]
    assert one(db, "SELECT count(*) FROM ZWAMESSAGE WHERE ZCHATSESSION = ?", pk)[0] == 5


def test_direction_is_written_the_way_whatsapp_does(converted):
    _, _, db = converted
    incoming = one(db, "SELECT * FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-in'")
    outgoing = one(db, "SELECT * FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-out'")
    assert (incoming["ZISFROMME"], incoming["ZFROMJID"], incoming["ZTOJID"], incoming["ZMESSAGESTATUS"]) == \
        (0, "32470000111@s.whatsapp.net", None, 0)
    assert (outgoing["ZISFROMME"], outgoing["ZFROMJID"], outgoing["ZTOJID"], outgoing["ZMESSAGESTATUS"]) == \
        (1, None, "32470000111@s.whatsapp.net", 8)
    assert outgoing["ZPUSHNAME"] == "Me" and outgoing["ZSTARRED"] == 1
    assert incoming["ZMESSAGEDATE"] == pytest.approx((T0 + 1000) / 1000 - APPLE)
    assert (incoming["ZTEXT"], incoming["Z_ENT"], incoming["ZFLAGS"]) == ("hello", 9, 16777216)


def test_group_senders_are_matched_by_privacy_id_or_added(converted):
    _, _, db = converted
    known = one(db, "SELECT * FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-g1'")
    past = one(db, "SELECT * FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-g2'")
    assert known["ZGROUPMEMBER"] == 1 and known["ZFROMJID"] == "120363000@g.us"
    member = one(db, "SELECT * FROM ZWAGROUPMEMBER WHERE Z_PK = ?", past["ZGROUPMEMBER"])
    assert (member["ZMEMBERJID"], member["ZISACTIVE"], member["ZCHATSESSION"]) == ("32470000333@s.whatsapp.net", 0, 1)
    sent = one(db, "SELECT * FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-g3'")
    assert (sent["ZTOJID"], sent["ZGROUPMEMBER"]) == ("120363000@g.us", None)


def test_history_goes_to_the_live_chat_not_a_deleted_one(inputs):
    """A deleted session for the group, made after the live one, is passed over."""
    android, ios, media = inputs
    with closing(sqlite3.connect(ios)) as db:
        db.execute("INSERT INTO ZWACHATSESSION (Z_PK, Z_ENT, ZSESSIONTYPE, ZCONTACTJID, ZPARTNERNAME, ZREMOVED) "
                   "VALUES (9, 4, 1, '120363000@g.us', 'Family', 1)")
        db.commit()
    _, run = convert.convert(android, ios, media, ACCOUNT)
    with closing(sqlite3.connect(run / "files" / "ChatStorage.sqlite")) as db:
        assert one(db, "SELECT ZCHATSESSION FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-g1'")[0] == 1


def test_history_sorts_before_what_the_account_already_had(converted):
    _, _, db = converted
    order = [r[0] for r in db.execute("SELECT ZSTANZAID FROM ZWAMESSAGE WHERE ZCHATSESSION = 1 ORDER BY ZSORT")]
    assert order == ["k-g1", "k-g2", "k-g3", "k-g4", "k-g5", "sys1"]
    session = one(db, "SELECT * FROM ZWACHATSESSION WHERE Z_PK = 1")
    assert session["ZLASTMESSAGE"] == 1 and session["ZMESSAGECOUNTER"] == 6


def test_media_rows_and_files(converted, inputs):
    report, run, db = converted
    image = one(db, "SELECT i.* FROM ZWAMEDIAITEM i JOIN ZWAMESSAGE m ON m.ZMEDIAITEM = i.Z_PK WHERE m.ZSTANZAID = 'k-img'")
    assert (image["ZLATITUDE"], image["ZLONGITUDE"], image["ZTITLE"], image["ZFILESIZE"]) == (2048.0, 1536.0, "a caption", 1234)
    path = image["ZMEDIALOCALPATH"]
    assert path.startswith("Media/32470000111@s.whatsapp.net/") and path.endswith(".jpg")
    placed = run / "files" / ACCOUNT / "Message" / path
    assert placed.read_bytes() == b"\xff\xd8 a jpeg"
    # Android gave no hash here, so it's the placed file's SHA-256, as WhatsApp keeps it.
    assert image["ZVCARDNAME"] == base64.b64encode(hashlib.sha256(b"\xff\xd8 a jpeg").digest()).decode()
    assert (image["ZASPECTRATIO"], image["ZMOVIEDURATION"]) == (0.0, 0)
    video = one(db, "SELECT i.* FROM ZWAMEDIAITEM i JOIN ZWAMESSAGE m ON m.ZMEDIAITEM = i.Z_PK WHERE m.ZSTANZAID = 'k-vid'")
    assert video["ZMEDIALOCALPATH"] is None and video["ZMOVIEDURATION"] == 12
    voice = one(db, "SELECT m.ZMESSAGETYPE, i.ZMOVIEDURATION FROM ZWAMESSAGE m JOIN ZWAMEDIAITEM i ON i.Z_PK = m.ZMEDIAITEM "
                    "WHERE m.ZSTANZAID = 'k-voice'")
    assert tuple(voice) == (3, 5)
    assert (report.media_files_copied, report.media_files_missing) == (2, 1)


def test_locations_cards_and_deleted(converted):
    _, _, db = converted
    loc = one(db, "SELECT i.* FROM ZWAMEDIAITEM i JOIN ZWAMESSAGE m ON m.ZMEDIAITEM = i.Z_PK WHERE m.ZSTANZAID = 'k-g3'")
    assert (loc["ZLATITUDE"], loc["ZLONGITUDE"], loc["ZTITLE"]) == (50.85, 4.35, "Brussels")
    card = one(db, "SELECT i.* FROM ZWAMEDIAITEM i JOIN ZWAMESSAGE m ON m.ZMEDIAITEM = i.Z_PK WHERE m.ZSTANZAID = 'k-g4'")
    assert card["ZVCARDNAME"] == "Bob" and "FN:Bob" in card["ZVCARDSTRING"]
    deleted = one(db, "SELECT ZMESSAGETYPE, ZTEXT, ZMEDIAITEM FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-g5'")
    assert tuple(deleted) == (14, None, None)


def test_primary_keys_stay_ahead(converted):
    _, _, db = converted
    for name, table in (("WAMessage", "ZWAMESSAGE"), ("WAMediaItem", "ZWAMEDIAITEM"), ("WAChatSession", "ZWACHATSESSION"),
                        ("WAGroupMember", "ZWAGROUPMEMBER")):
        z_max = one(db, "SELECT Z_MAX FROM Z_PRIMARYKEY WHERE Z_NAME = ?", name)[0]
        assert z_max == one(db, f"SELECT max(Z_PK) FROM {table}")[0], name


def test_inputs_are_left_untouched(inputs):
    android, ios, media = inputs
    before = [android.read_bytes(), ios.read_bytes()]
    convert.convert(android, ios, media, ACCOUNT)
    assert [android.read_bytes(), ios.read_bytes()] == before


def test_running_on_its_own_output_adds_nothing(converted, inputs):
    android, _, media = inputs
    _, run, _ = converted
    again, run2 = convert.convert(android, run / "files" / "ChatStorage.sqlite", media, ACCOUNT)
    assert again.converted == {} and again.already_there == 10
    assert again.checks["messages"] == 11  # the account's one notice plus the ten converted


def test_main_account_media_goes_under_message_media(inputs):
    android, ios, media = inputs
    report, run = convert.convert(android, ios, media, None)
    assert list((run / "files" / "Message" / "Media").rglob("*.jpg"))


def test_not_a_chat_database(tmp_path, inputs):
    android, _, media = inputs
    other = make_sqlite(tmp_path / "other.sqlite", "CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR, Z_SUPER INTEGER, Z_MAX INTEGER);")
    with pytest.raises(convert.ConvertError, match="not a WhatsApp ChatStorage"):
        convert.convert(android, other, media)


def test_cli(inputs, capsys):
    android, ios, media = inputs
    assert main(["convert", str(android), str(ios), "--media", str(media), "--account-folder", ACCOUNT]) == 0
    out = capsys.readouterr().out
    assert "Converted 10 of 14 Android messages" in out and "no problems" in out
    for secret in ("hello", "from a member", "Brussels"):
        assert secret not in out
