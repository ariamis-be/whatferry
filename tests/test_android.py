import os
import stat
import sys
import zlib

import pytest
from wa_crypt_tools.lib.db.db14 import Database14
from wa_crypt_tools.lib.db.db15 import Database15
from wa_crypt_tools.lib.key.keyfactory import KeyFactory
from wa_crypt_tools.lib.props import Props

from conftest import make_sqlite
from whatferry import android
from whatferry.cli import main

KEY = "0123456789abcdef" * 4
OTHER_KEY = "fedcba9876543210" * 4


@pytest.fixture
def msgstore(tmp_path):
    return make_sqlite(tmp_path / "msgstore.db", """
        PRAGMA user_version = 1;
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, raw_string TEXT);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT);
        CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER,
                              timestamp INTEGER, message_type INTEGER, text_data TEXT);
        CREATE TABLE message_media (message_row_id INTEGER PRIMARY KEY, file_path TEXT);
        INSERT INTO jid VALUES (1, '32470000001', 's.whatsapp.net', '32470000001@s.whatsapp.net'),
                               (2, '120363000', 'g.us', '120363000@g.us'),
                               (3, '98765', 'lid', '98765@lid');
        INSERT INTO chat VALUES (1, 1, NULL), (2, 2, 'Family');
        INSERT INTO message VALUES (1, 1, 1, 1700000000000, 0, 'hello'),
                                   (2, 1, 0, 1700000060000, 0, 'hi'),
                                   (3, 2, 0, 1760000000000, 1, NULL);
        INSERT INTO message_media VALUES (3, 'Media/WhatsApp Images/IMG-1.jpg');
    """)


def encrypt(plain_db, out, key_hex=KEY):
    key = KeyFactory.from_hex(key_hex)
    data = Database15(key=key).encrypt(key, Props(wa_version="2.26.20.10", jid="42"),
                                       zlib.compress(plain_db.read_bytes(), 1))
    out.write_bytes(data)
    return out


def test_decrypts_crypt15_and_describes_it(msgstore, tmp_path):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    report, run = android.inspect(backup, android.parse_key(KEY))

    assert report.header.app_version == "2.26.20.10"
    assert report.header.number_ends_with == "42"
    assert report.layout.startswith("modern")
    assert report.counts["chats"] == 2
    assert report.counts["messages"] == 3
    assert report.counts["media"] == 1
    assert report.counts["calls"] is None
    assert report.jid_servers == {"s.whatsapp.net": 1, "g.us": 1, "lid": 1}
    assert report.message_types == {0: 2, 1: 1}
    assert report.first_message == "2023-11-14T22:13:20+00:00"
    assert (run / "msgstore.db").read_bytes() == msgstore.read_bytes()
    assert "CREATE TABLE message" in (run / "schema.sql").read_text()


def test_key_is_accepted_with_the_spaces_whatsapp_shows(msgstore, tmp_path):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    spaced = " ".join(KEY.upper()[i:i + 4] for i in range(0, 64, 4))
    report, _ = android.inspect(backup, android.parse_key(spaced))
    assert report.counts["messages"] == 3


def test_wrong_key_is_refused_not_written(msgstore, tmp_path, private_home):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    with pytest.raises(android.DecryptError, match="key does not match"):
        android.inspect(backup, android.parse_key(OTHER_KEY))
    assert not list(private_home.glob("*/msgstore.db"))


def test_a_crypt14_backup_with_the_64_digit_key_says_why(tmp_path, monkeypatch):
    backup = tmp_path / "msgstore.db.crypt14"
    backup.write_bytes(b"a crypt14 file")
    monkeypatch.setattr(android.DatabaseFactory, "from_file", staticmethod(lambda f: Database14()))
    with pytest.raises(android.DecryptError, match="crypt14 backup: its key only exists on a rooted phone"):
        android.decrypt(backup, android.parse_key(KEY))


def test_a_header_the_library_cant_place_is_a_decrypt_error(tmp_path, monkeypatch):
    backup = tmp_path / "msgstore.db.crypt15"
    backup.write_bytes(b"not a backup")
    monkeypatch.setattr(android.DatabaseFactory, "from_file", staticmethod(lambda f: None))
    with pytest.raises(android.DecryptError, match="not a WhatsApp crypt14/15 backup"):
        android.decrypt(backup, android.parse_key(KEY))


@pytest.mark.parametrize("text", ["", "123", "g" * 64, KEY + "0"])
def test_malformed_keys_are_refused(text):
    with pytest.raises(android.DecryptError, match="64 hexadecimal"):
        android.parse_key(text)


def test_key_file_holding_the_64_digit_key(msgstore, tmp_path):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    key_file = tmp_path / "key.txt"
    key_file.write_text(KEY + "\n")
    report, _ = android.inspect(backup, android.load_key(key_file))
    assert report.counts["chats"] == 2


def test_already_decrypted_database_needs_no_key(msgstore):
    report, _ = android.inspect(msgstore, None)
    assert report.header is None
    assert report.counts["messages"] == 3


def test_encrypted_backup_without_key_is_refused(msgstore, tmp_path):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    with pytest.raises(android.DecryptError, match="--key-file"):
        android.inspect(backup, None)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no Unix modes; the profile's ACL protects it")
def test_run_folder_is_private(msgstore):
    _, run = android.inspect(msgstore, None)
    assert stat.S_IMODE(run.stat().st_mode) == 0o700
    assert stat.S_IMODE(run.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE((run / "msgstore.db").stat().st_mode) == 0o600


def test_cli_prints_counts_but_no_message_text(msgstore, tmp_path, capsys):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    key_file = tmp_path / "key.txt"
    key_file.write_text(KEY)
    assert main(["android", "inspect", str(backup), "--key-file", str(key_file)]) == 0
    out = capsys.readouterr().out
    assert "messages" in out and "3" in out
    assert "number ending in 42" in out
    for secret in ("hello", "Family", "32470000001", KEY):
        assert secret not in out


def test_cli_reads_key_from_environment(msgstore, tmp_path, monkeypatch, capsys):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    monkeypatch.setenv("WHATFERRY_ANDROID_KEY", KEY)
    assert main(["android", "inspect", str(backup)]) == 0


def test_cli_wrong_key_exits_with_message(msgstore, tmp_path, monkeypatch, capsys):
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    monkeypatch.setenv("WHATFERRY_ANDROID_KEY", OTHER_KEY)
    assert main(["android", "inspect", str(backup)]) == 1
    assert "key does not match" in capsys.readouterr().err


def test_legacy_layout_is_flagged(tmp_path):
    db = make_sqlite(tmp_path / "old.db", "CREATE TABLE messages (_id INTEGER PRIMARY KEY, key_remote_jid TEXT);")
    report, _ = android.inspect(db, None)
    assert report.layout.startswith("legacy")
    assert os.path.exists(db)
