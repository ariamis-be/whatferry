"""The wizard's iPhone -> Android direction, end to end, with a stand-in phone."""

import sys
from pathlib import Path

import pytest

from conftest import make_sqlite
from encrypted_backup import make_encrypted_backup
from test_android import KEY, encrypt
from test_convert import ACCOUNT
from test_to_android import FAKE_PHONE_ADB, TEMPLATE, iphone  # noqa: F401 - fixture
from whatferry import adb
from whatferry.backup_writer import SHARED_DOMAIN as SHARED
from whatferry.ui.wizard import StepError, Wizard

PASS = "correct horse"
UDID = "00008160-0077"


@pytest.fixture
def wizard(iphone, tmp_path, private_home, monkeypatch):  # noqa: F811
    """Android backup checked (crypt15 + key), iPhone backup checked, direction iPhone -> Android."""
    ios_db, media = iphone
    files = {(SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): ios_db.read_bytes()}
    # The photos and videos inside the iPhone backup, where the account keeps them.
    convert_files = ios_db.parent / "Message"
    for path in (p for p in convert_files.rglob("*") if p.is_file()):
        files[(SHARED, f"{ACCOUNT}/Message/{path.relative_to(convert_files).as_posix()}")] = path.read_bytes()
    backup = make_encrypted_backup(tmp_path / "backups" / UDID, PASS, files,
                                   folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    android_backup = encrypt(make_sqlite(tmp_path / "template.db", TEMPLATE),
                             tmp_path / "whatsapp-account-1001-msgstore.db.crypt15")
    w = Wizard(private_home)
    w.set_direction("to-android")
    w.ios_inspect(str(backup), PASS, "before")
    w.android_inspect(str(android_backup), KEY)
    return w


def test_direction_switch_drops_the_transfer(wizard):
    wizard.make_conversion(ACCOUNT, None)
    assert wizard.state.get()["converted"]
    wizard.set_direction("to-android")  # same direction: kept
    assert wizard.state.get()["converted"]
    wizard.set_direction("to-iphone")
    assert not wizard.state.get().get("converted")
    with pytest.raises(StepError):
        wizard.set_direction("sideways")


def test_iphone_to_android_end_to_end(wizard, tmp_path, monkeypatch):
    options = wizard.convert_options()
    assert options["direction"] == "to-android" and options["android_ready"] and options["encrypted"]
    assert [t["folder"] for t in options["targets"]] == [ACCOUNT]

    converted = wizard.make_conversion(ACCOUNT, "backup", PASS)
    report = converted["report"]
    assert report["media_files_copied"] == 3 and report["direction"] == "iphone-to-android"

    found = wizard.preview_chats()
    assert found["totals"]["new"] == 2 and found["totals"]["moved"] == sum(report["converted"].values())
    group = next(c for c in found["chats"] if c["group"])
    messages = wizard.preview_messages(group["id"])["messages"]
    assert any(m["sender"] for m in messages) and all(m["moved"] for m in messages)
    picture = next(m for c in found["chats"] for m in wizard.preview_messages(c["id"])["messages"] if m["picture"])
    assert wizard.preview_picture(picture["id"])["data"].startswith("data:image/jpeg;base64,")

    with pytest.raises(Exception, match="64 hexadecimal"):
        wizard.write_backup("not a key")
    written = wizard.write_backup(KEY)
    assert written["report"]["verified"] and Path(written["folder"]).name == "WhatsApp"

    # The stand-in phone: WhatsApp's folders on disk.
    phone = tmp_path / "phone"
    (phone / "Android/media/com.whatsapp/WhatsApp/Databases").mkdir(parents=True)
    tool = tmp_path / "bin" / "adb"
    tool.parent.mkdir()
    tool.write_text(FAKE_PHONE_ADB.format(python=sys.executable))
    tool.chmod(0o755)
    monkeypatch.setenv("FAKE_PHONE", str(phone))
    monkeypatch.setenv("WHATFERRY_ADB", str(tool))

    status = wizard.restore_status()
    assert status["direction"] == "to-android"
    assert status["devices"][0]["folders"] == [adb.WHATSAPP_ROOT]
    assert status["suggested_folder"] == f"{adb.WHATSAPP_ROOT}/accounts/1001"
    with pytest.raises(StepError, match="confirm"):
        wizard.restore_backup(None, False, serial="PHONE1", folder=adb.WHATSAPP_ROOT)
    restored = wizard.restore_backup(None, True, serial="PHONE1", folder=adb.WHATSAPP_ROOT)
    assert restored["media_files"] == 3 and restored["kept"] is None
    on_phone = phone / "Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15"
    assert on_phone.read_bytes() == (Path(written["folder"]) / "Databases/msgstore.db.crypt15").read_bytes()


def test_only_the_encrypted_android_backup_can_be_written_back(iphone, tmp_path, private_home):  # noqa: F811
    ios_db, _ = iphone
    backup = make_encrypted_backup(tmp_path / "backups" / UDID, PASS,
                                   {(SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): ios_db.read_bytes()},
                                   folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    w = Wizard(private_home)
    w.set_direction("to-android")
    w.ios_inspect(str(backup), PASS, "before")
    w.android_inspect(str(make_sqlite(tmp_path / "msgstore.db", TEMPLATE)), None)  # already decrypted
    assert not w.convert_options()["android_ready"]
    with pytest.raises(StepError, match="end-to-end encrypted"):
        w.make_conversion(ACCOUNT, None)
