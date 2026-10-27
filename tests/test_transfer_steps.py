"""The wizard's last three steps: convert, write, restore. The phone is a stand-in."""

import plistlib
from pathlib import Path

import pytest

from conftest import make_sqlite
from encrypted_backup import make_encrypted_backup
from test_convert import ACCOUNT, ANDROID, IOS
from whatferry import restore
from whatferry.backup_writer import SHARED_DOMAIN as SHARED, WriteError
from whatferry.cli import main
from whatferry.ios_backup import Backup, WrongPassphrase
from whatferry.restore import Iphone, RestoreError
from whatferry.ui.wizard import STEPS, StepError, Wizard

PASS = "correct horse"
UDID = "00008160-0020"


class FakePhone:
    """Stands in for usbmuxd and the iPhone: records what a restore was asked to do."""

    def __init__(self, monkeypatch, **phone):
        self.phone = Iphone(**({"udid": UDID, "name": "Test iPhone", "ios_version": "27.0.1", "paired": True,
                                "find_my": False} | phone))
        self.restored = []

        async def listing():
            return [self.phone]

        async def run(backups, udid, passphrase, progress):
            progress(50.0)
            progress(100.0)
            self.restored.append((backups, udid, passphrase))

        monkeypatch.setattr(restore, "_list", listing)
        monkeypatch.setattr(restore, "_restore", run)


@pytest.fixture
def wizard(private_home, tmp_path):
    """Both backups checked, with the second account's chat database in the iPhone one."""
    w = Wizard(private_home)
    w.android_inspect(str(make_sqlite(tmp_path / "msgstore.db", ANDROID)), None)
    backup = make_encrypted_backup(tmp_path / "backups" / UDID, PASS, {
        (SHARED, "ChatStorage.sqlite"): make_sqlite(tmp_path / "main.sqlite", IOS).read_bytes(),
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): make_sqlite(tmp_path / "second.sqlite", IOS).read_bytes(),
    }, folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    w.ios_inspect(str(backup), PASS, "before")
    return w


def test_steps_run_in_order():
    assert STEPS[-4:] == ("convert", "write", "restore", "done")


def test_convert_options_list_the_accounts_and_media(wizard, tmp_path, monkeypatch):
    media = tmp_path / "user" / "whatferry-android" / "media"
    for account in ("account-1001", "account-1002"):
        (media / account / "WhatsApp Images").mkdir(parents=True)
    # The history names Media/WhatsApp Images/Sent/IMG-1.jpg: only account-1001 has it.
    (media / "account-1001" / "WhatsApp Images" / "Sent").mkdir()
    (media / "account-1001" / "WhatsApp Images" / "Sent" / "IMG-1.jpg").write_bytes(b"\xff\xd8")
    monkeypatch.setenv("HOME", str(tmp_path / "user"))

    options = wizard.convert_options()
    assert [t["folder"] for t in options["targets"]] == [None, ACCOUNT]
    picked = {m["name"]: m["suggested"] for m in options["media"]}
    assert picked == {"account-1001": True, "account-1002": False}


def test_convert_write_restore(wizard, tmp_path, monkeypatch):
    converted = wizard.make_conversion(ACCOUNT, None)
    assert converted["account_folder"] == ACCOUNT and converted["report"]["source_sha256"]

    with pytest.raises(WrongPassphrase):
        wizard.write_backup("nope")
    written = wizard.write_backup(PASS)
    assert written["report"]["verified_files"] == 1
    target = Backup(Path(written["folder"]), PASS)
    assert any(e.path == f"{ACCOUNT}/ChatStorage.sqlite" for e in target.entries())

    phone = FakePhone(monkeypatch)
    status = wizard.restore_status()
    assert status["udid"] == UDID and status["phones"][0]["name"] == "Test iPhone"
    with pytest.raises(StepError, match="confirm"):
        wizard.restore_backup(PASS, False)
    with pytest.raises(WrongPassphrase):
        wizard.restore_backup("nope", True)
    assert phone.restored == [], "nothing reaches the phone before the passphrase is right"

    seen = []
    restored = wizard.restore_backup(PASS, True, seen.append)
    assert phone.restored == [(target.folder.parent, UDID, PASS)]
    assert seen == [50.0, 100.0] and restored["phone"] == "Test iPhone"
    assert wizard.state.get()["restored"]["folder"] == written["folder"]


def test_redoing_a_step_drops_the_later_ones(wizard, monkeypatch):
    wizard.make_conversion(ACCOUNT, None)
    wizard.write_backup(PASS)
    FakePhone(monkeypatch)
    wizard.restore_backup(PASS, True)
    wizard.make_conversion(ACCOUNT, None)
    state = wizard.state.get()
    assert state["converted"] and not state.get("written") and not state.get("restored")


def test_steps_out_of_order_are_refused(private_home):
    w = Wizard(private_home)
    with pytest.raises(StepError):
        w.convert_options()
    with pytest.raises(StepError):
        w.write_backup(PASS)
    with pytest.raises(StepError):
        w.restore_backup(PASS, True)


def test_convert_only_into_an_account_of_the_checked_backup(wizard):
    with pytest.raises(StepError, match="isn't in the checked backup"):
        wizard.make_conversion("data/SOMETHING-ELSE", None)


def test_write_guard_and_its_override(wizard, tmp_path):
    """A second, newer backup checked after converting: the guard refuses, the override writes."""
    wizard.make_conversion(ACCOUNT, None)
    converted = wizard.state.get()["converted"]
    newer = make_encrypted_backup(tmp_path / "newer" / UDID, PASS, {
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"):
            make_sqlite(tmp_path / "moved-on.sqlite", IOS + "\nPRAGMA user_version = 9;").read_bytes(),
    }, folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    wizard.state.update(converted=converted | {"backup": str(newer)})
    with pytest.raises(WriteError, match="isn't the one the conversion was made"):
        wizard.write_backup(PASS)
    assert wizard.write_backup(PASS, skip_source_check=True)["report"]["source_checked"] is False


def test_reset_forgets_the_transfer_too(wizard):
    wizard.make_conversion(ACCOUNT, None)
    wizard.reset()
    state = wizard.state.get()
    assert not state.get("converted") and not state.get("accounts")


def test_the_steps_over_http(wizard, monkeypatch):
    """Convert, write and restore as the page runs them, restore reporting progress."""
    import threading

    from test_ui import request, run
    from whatferry.ui.server import Server

    FakePhone(monkeypatch)
    srv = Server(wizard)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    try:
        assert request(srv, "POST", "/api/write", {"passphrase": PASS})[0] == 202  # a job, which fails:
        assert "convert first" in run(srv, "/api/write", {"passphrase": PASS})["error"]
        options = request(srv, "GET", "/api/convert/options")[2]
        assert [t["folder"] for t in options["targets"]] == [None, ACCOUNT]
        assert run(srv, "/api/convert", {"account_folder": ACCOUNT, "media": None})["status"] == "done"
        assert run(srv, "/api/write", {"passphrase": PASS})["status"] == "done"
        status = request(srv, "GET", "/api/restore/status")[2]
        assert status["udid"] == UDID and status["phones"][0]["find_my"] is False
        assert "confirm" in run(srv, "/api/restore", {"passphrase": PASS, "confirmed": "yes"})["error"]
        job = run(srv, "/api/restore", {"passphrase": PASS, "confirmed": True})
        assert job["status"] == "done" and job["progress"] == 100.0
        assert request(srv, "GET", "/api/overview")[2]["state"]["restored"]
    finally:
        srv.shutdown()
        srv.server_close()


# restore.restore: what it refuses before anything reaches the phone

@pytest.fixture
def written(tmp_path):
    return make_encrypted_backup(tmp_path / "out" / UDID, PASS, {(SHARED, "x"): b"x"})


@pytest.mark.parametrize("phone, message", [
    ({"udid": "00008160-9999"}, "connect the iPhone this backup is from"),
    ({"paired": False}, "isn't trusted"),
    ({"find_my": True}, "Find My is on"),
])
def test_restore_refuses(written, monkeypatch, phone, message):
    fake = FakePhone(monkeypatch, **phone)
    with pytest.raises(RestoreError, match=message):
        restore.restore(written, PASS)
    assert fake.restored == []


def test_restore_needs_the_passphrase_of_an_encrypted_backup(written, monkeypatch):
    fake = FakePhone(monkeypatch)
    with pytest.raises(RestoreError, match="passphrase"):
        restore.restore(written, None)
    assert fake.restored == []


def test_restore_refuses_another_iphones_backup(written):
    info = plistlib.loads((written / "Info.plist").read_bytes())
    (written / "Info.plist").write_bytes(plistlib.dumps(info | {"Target Identifier": "00008160-OTHER"}))
    with pytest.raises(RestoreError, match="another iPhone"):
        restore.backup_udid(written)


def test_restore_passes_the_phones_reason_on(written, monkeypatch):
    FakePhone(monkeypatch)

    async def refuses(*_):
        raise RuntimeError("MBErrorDomain/211: Find My iPhone must be turned off")

    monkeypatch.setattr(restore, "_restore", refuses)
    with pytest.raises(RestoreError, match="stopped the restore: MBErrorDomain/211"):
        restore.restore(written, PASS)


def test_cli_restore_asks_for_the_name(written, monkeypatch, capsys):
    fake = FakePhone(monkeypatch)
    monkeypatch.setenv("WHATFERRY_BACKUP_PASSPHRASE", PASS)
    monkeypatch.setattr("builtins.input", lambda _: "not it")
    assert main(["ios", "restore", str(written)]) == 1
    assert fake.restored == [] and "Not restored" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda _: "Test iPhone")
    assert main(["ios", "restore", str(written)]) == 0
    assert fake.restored == [(written.parent, UDID, PASS)]
    assert "Restored" in capsys.readouterr().out
