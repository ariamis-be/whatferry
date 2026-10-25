"""Which iPhone account the Android chats go to, and how the wizard suggests it."""

import plistlib
import sqlite3
import struct
from datetime import datetime
from contextlib import closing

import pytest

from conftest import FakeBackup
from test_ios import APP, SHARED, chat_storage
from test_ui import request, run, server  # noqa: F401 - fixture
from whatferry import ios
from whatferry.ios_backup import Backup
from whatferry.ui.wizard import destination_hint, summary_text

MAIN_ID, SECOND_ID = "267817232396200", "263779778617311"
OWN_NUMBER, CONTACT_NUMBER = "40700001234", "32470000188"
FOLDER = "data/0A1B2C3D-4E5F-4A6B-8C7D-9E0F1A2B3C4D"
PREFS = "Library/Preferences/group.net.whatsapp.WhatsApp.shared.plist"


def lid_db(path, rows):
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE ZWAZACCOUNT (Z_PK INTEGER PRIMARY KEY, ZIDENTIFIER VARCHAR, "
                   "ZPHONENUMBER VARCHAR, ZCOUNTRYCODE VARCHAR)")
        db.executemany("INSERT INTO ZWAZACCOUNT (ZIDENTIFIER, ZPHONENUMBER, ZCOUNTRYCODE) VALUES (?, ?, ?)", rows)
        db.commit()
    return path.read_bytes()


def shared_prefs(own_jid):
    """WhatsApp's shared preferences, with a date Python's plistlib can't hold,
    as the real file has: plistlib.loads rejects the whole file."""
    marker = datetime(2001, 1, 1, 0, 0, 7)
    data = plistlib.dumps({"LastOwnJabberID": own_jid, "SomeExpiry": marker}, fmt=plistlib.FMT_BINARY)
    data = data.replace(b"\x33" + struct.pack(">d", 7.0), b"\x33" + struct.pack(">d", 1e20))
    with pytest.raises(plistlib.InvalidFileException):
        plistlib.loads(data)
    return data


def two_account_iphone(tmp_path, root):
    """Like the real one: signed in as …1234, a data/<id> folder for what may be
    a second account, and two traps that once passed for accounts: a keyboard
    entry and a profile-name row, both a contact's (…0188)."""
    fake = FakeBackup(root / "UDID")
    chat_storage(tmp_path / "ChatStorage.sqlite", messages=4)
    with closing(sqlite3.connect(tmp_path / "ChatStorage.sqlite")) as db:
        db.execute("CREATE TABLE ZWAPROFILEPUSHNAME (Z_PK INTEGER PRIMARY KEY, ZJID VARCHAR, ZPUSHNAME VARCHAR)")
        db.execute("INSERT INTO ZWAPROFILEPUSHNAME VALUES (1, ?, 'A contact')", (f"{SECOND_ID}@lid",))
        db.commit()
    fake.add(SHARED, "ChatStorage.sqlite", (tmp_path / "ChatStorage.sqlite").read_bytes())
    fake.add(SHARED, "LID.sqlite", lid_db(tmp_path / "LID.sqlite", [
        (f"{MAIN_ID}@lid", OWN_NUMBER, "RO"),
        (f"{SECOND_ID}@lid", CONTACT_NUMBER, "BE"),
    ]))
    fake.add(SHARED, PREFS, shared_prefs(f"{OWN_NUMBER}@s.whatsapp.net"))
    keyboard = {f"ID_{MAIN_ID}@lid": "en_GB", f"ID_{SECOND_ID}@lid": "en_GB"}
    fake.add(APP, "Library/Preferences/UITextInputContextIdentifiers.plist",
             plistlib.dumps(keyboard, fmt=plistlib.FMT_BINARY))
    fake.add(SHARED, f"{FOLDER}/ContactsV2.sqlite", b"not sqlite")
    fake.add(SHARED, f"{FOLDER}/backup_control_file", b"")
    return fake


def test_signed_in_account_from_last_own_jabber_id(tmp_path):
    fake = two_account_iphone(tmp_path, tmp_path / "backups")
    report, _ = ios.inspect(Backup(fake.folder))
    assert [(a.id_ends, a.number_ends, a.country, a.main) for a in report.accounts] == [("00", "1234", "RO", True)]
    assert [(f.folder, f.has_chat_database) for f in report.account_folders] == [(FOLDER, False)]
    assert report.accounts_method == ios.ACCOUNTS_METHOD == 3


def test_contacts_never_pass_for_accounts(tmp_path):
    """Both a keyboard entry and the profile-name row belonged to contacts on a
    real backup. Neither may turn into an account, and no long digits leak."""
    fake = two_account_iphone(tmp_path, tmp_path / "backups")
    report, _ = ios.inspect(Backup(fake.folder))
    assert all(not (a.number_ends or "").endswith("0188") for a in report.accounts)
    text = str(report.as_dict())
    for secret in (MAIN_ID, SECOND_ID, OWN_NUMBER, CONTACT_NUMBER):
        assert secret not in text


def test_number_without_lid_database(tmp_path):
    fake = FakeBackup(tmp_path / "UDID")
    fake.add(SHARED, PREFS, shared_prefs(f"{OWN_NUMBER}@s.whatsapp.net"))
    report, _ = ios.inspect(Backup(fake.folder))
    assert [(a.id_ends, a.number_ends, a.country) for a in report.accounts] == [(None, "1234", None)]


@pytest.mark.parametrize("prefs", [b"not a plist", None])
def test_accounts_tolerate_a_bare_backup(tmp_path, prefs):
    fake = FakeBackup(tmp_path / "UDID")
    store, _ = chat_storage(tmp_path / "ChatStorage.sqlite", messages=1)
    fake.add(SHARED, "ChatStorage.sqlite", store)
    if prefs is not None:
        fake.add(SHARED, PREFS, prefs)
    report, _ = ios.inspect(Backup(fake.folder))
    assert report.accounts == [] and report.account_folders == []


def test_lenient_plist_reader_keeps_what_it_can():
    data = shared_prefs("123456789@s.whatsapp.net")
    parsed = ios.read_plist(data)
    assert parsed["LastOwnJabberID"] == "123456789@s.whatsapp.net" and parsed["SomeExpiry"] is None
    assert ios.read_plist(b"garbage") is None


def state(android_ends=None, accounts=(), stores=("ChatStorage.sqlite",), messages=10):
    databases = [{"path": p, "counts": {"messages": messages}} for p in stores]
    return {
        "android": {"report": {"header": {"number_ends_with": android_ends}}} if android_ends else None,
        "before": {"report": {"accounts": list(accounts), "databases": databases, "accounts_method": 3}},
    }


ACCOUNTS = [{"id_ends": "00", "number_ends": "0102", "main": True},
            {"id_ends": "11", "number_ends": "0188", "main": False}]


def test_no_hint_before_the_first_backup():
    assert destination_hint({}) is None


def test_no_whatsapp_suggests_setting_it_up():
    hint = destination_hint(state("78", accounts=[], stores=[]))
    assert (hint["suggested"], hint["reason"]) == ("setup", "no-whatsapp")


def test_different_number_suggests_a_second_account_and_flags_a_full_phone():
    hint = destination_hint(state("78", ACCOUNTS))
    assert (hint["suggested"], hint["reason"], hint["full"]) == ("second", "different-number", True)
    one = destination_hint(state("78", ACCOUNTS[:1]))
    assert one["suggested"] == "second" and not one["full"]


def test_an_extra_account_folder_means_there_may_already_be_two():
    s = state("78", ACCOUNTS[:1])
    assert not destination_hint(s)["full"]
    s["before"]["report"]["account_folders"] = [{"folder": FOLDER, "has_chat_database": False}]
    assert destination_hint(s)["full"]


def test_matching_number_suggests_the_existing_account_with_its_chats():
    hint = destination_hint(state("02", ACCOUNTS, messages=483343))
    assert (hint["suggested"], hint["reason"]) == ("existing", "number-matches")
    assert hint["match"]["id_ends"] == "00" and hint["messages"] == 483343
    second = destination_hint(state("88", ACCOUNTS))
    assert second["match"]["id_ends"] == "11" and second["messages"] is None


@pytest.mark.parametrize("method", [None, 1, 2])
def test_checks_from_older_account_detection_say_check_again(method):
    """None: saved before accounts were read; 1: the keyboard-file method,
    which mistook a chat for an account. Both must ask for a new check."""
    s = state("78", ACCOUNTS)
    if method is None:
        del s["before"]["report"]["accounts_method"]
        del s["before"]["report"]["accounts"]
    else:
        s["before"]["report"]["accounts_method"] = method
    hint = destination_hint(s)
    assert (hint["suggested"], hint["reason"], hint["stale"]) == ("second", "stale-check", True)


def test_four_iphone_digits_match_the_android_two():
    hint = destination_hint(state("02", ACCOUNTS[:1]))
    assert hint["suggested"] == "existing" and hint["match"]["number_ends"] == "0102"
    assert destination_hint(state("12", ACCOUNTS[:1]))["suggested"] == "second"


def test_accounts_without_numbers_are_called_unknown():
    hint = destination_hint(state("78", [{"id_ends": "00", "number_ends": None, "main": True}]))
    assert hint["reason"] == "iphone-numbers-unknown" and not hint["stale"]


def test_hint_always_carries_the_main_account_s_messages():
    """Picking "existing" by hand must still warn about the merge, so the
    main account's message count comes with every hint, not only a match."""
    hint = destination_hint(state("78", ACCOUNTS[:1], messages=483343))
    assert hint["suggested"] == "second"
    assert hint["main_messages"] == 483343 and hint["has_whatsapp"]
    empty = destination_hint(state("78", accounts=[], stores=[]))
    assert empty["main_messages"] is None and not empty["has_whatsapp"]


def test_unknown_android_number_still_suggests_second():
    hint = destination_hint(state(None, ACCOUNTS))
    assert (hint["suggested"], hint["reason"]) == ("second", "unknown-number")


def test_choice_is_saved_validated_and_summarised(server):  # noqa: F811
    assert request(server, "POST", "/api/destination", {"choice": "elsewhere"})[0] == 400
    assert request(server, "POST", "/api/destination", {"choice": "existing"})[0] == 200
    _, _, overview = request(server, "GET", "/api/overview")
    assert overview["state"]["destination"] == "existing"
    assert overview["destination_hint"] is None
    request(server, "POST", "/api/reset", {})
    _, _, overview = request(server, "GET", "/api/overview")
    assert "destination" not in overview["state"]


def test_overview_hint_after_checking_the_iphone(server, tmp_path, monkeypatch):  # noqa: F811
    two_account_iphone(tmp_path, tmp_path / "backups")
    monkeypatch.setenv("WHATFERRY_BACKUP_ROOT", str(tmp_path / "backups"))
    assert run(server, "/api/ios/inspect", {"folder": "UDID", "role": "before"})["status"] == "done"
    _, _, overview = request(server, "GET", "/api/overview")
    hint = overview["destination_hint"]
    assert hint["suggested"] == "second" and hint["reason"] == "unknown-number" and hint["full"]


def test_summary_names_destination_and_accounts():
    s = state("78", ACCOUNTS)
    s["before"]["report"] |= {"device": {}, "domains": {}, "databases": [],
                              "account_folders": [{"folder": FOLDER, "has_chat_database": False}]}
    s["destination"] = "second"
    text = summary_text(s | {"android": None})
    assert "Destination: second (suggested: second, unknown-number)" in text
    assert "account id …00: number …0102, main chat database" in text
    assert "account folder data/0A1B2C3D…: no chat database" in text


@pytest.mark.parametrize("choice", ["setup", "second", "existing"])
def test_every_choice_is_accepted(server, choice):  # noqa: F811
    assert request(server, "POST", "/api/destination", {"choice": choice})[0] == 200
