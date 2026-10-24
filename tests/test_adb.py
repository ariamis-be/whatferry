"""adb support, against a fake adb that plays a phone with two WhatsApp accounts."""

import json
import stat
import sys
from pathlib import Path

import pytest

from whatferry import adb
from whatferry.cli import main

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake adb is a script with a shebang")

PHONE = {
    "/sdcard/Android/media/com.whatsapp/WhatsApp/accounts/1001/Databases/msgstore.db.crypt15": (4900000, 1761330000),
    "/sdcard/Android/media/com.whatsapp/WhatsApp/accounts/1001/Databases/msgstore-2026-10-24.1.db.crypt14": (5000000, 1761090000),
    "/sdcard/Android/media/com.whatsapp/WhatsApp/accounts/1002/Databases/msgstore.db.crypt14": (60000000, 1760830000),
    "/sdcard/Android/media/com.whatsapp/WhatsApp/accounts/1002/Databases/msgstore-increment-1.db.crypt14": (10000, 1760960000),
    "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business/Databases/msgstore.db.crypt15": (2048, 1761300000),
}

FAKE_ADB = """\
#!{python}
# A stand-in for adb: one ready Pixel and one phone waiting for Allow.
import json, os, sys
state = json.load(open(os.environ["FAKE_ADB_STATE"]))
args = sys.argv[1:]
if args == ["version"]:
    print("Android Debug Bridge version 1.0.41")
elif args == ["devices", "-l"]:
    print("List of devices attached")
    print("1A2B3C4D5E6F70         device usb:34816000X product:husky model:Pixel_8_Pro device:husky transport_id:1")
    print("R5CT1234567            unauthorized usb:1-2 transport_id:2")
elif args[:3] == ["-s", "1A2B3C4D5E6F70", "shell"]:
    assert "stat -c" in args[3], args
    for path, (size, mtime) in state["files"].items():
        print(f"{{size}}|{{mtime}}|{{path}}")
elif args[:3] == ["-s", "1A2B3C4D5E6F70", "pull"]:
    remote, local = args[3], args[4]
    with open(local, "wb") as f:
        f.write(("contents of " + remote).encode())
    print(f"{{remote}}: 1 file pulled")
else:
    print("unexpected", args, file=sys.stderr)
    sys.exit(1)
"""


@pytest.fixture
def fake_adb(tmp_path, monkeypatch):
    state = tmp_path / "phone.json"
    state.write_text(json.dumps({"files": PHONE}))
    tool = tmp_path / "bin" / "adb"
    tool.parent.mkdir()
    tool.write_text(FAKE_ADB.format(python=sys.executable))
    tool.chmod(0o755)
    monkeypatch.setenv("FAKE_ADB_STATE", str(state))
    monkeypatch.setenv("WHATFERRY_ADB", str(tool))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))
    return tool


def test_finds_a_working_adb_and_skips_a_broken_shim(tmp_path, fake_adb, monkeypatch):
    broken = tmp_path / "shims" / "adb"
    broken.parent.mkdir()
    broken.write_text("#!/bin/sh\necho 'No version is set for shim: adb' >&2\nexit 1\n")
    broken.chmod(0o755)
    sdk = tmp_path / "sdk" / "platform-tools"
    sdk.mkdir(parents=True)
    (sdk / "adb").write_text(fake_adb.read_text())
    (sdk / "adb").chmod(0o755)
    monkeypatch.setenv("PATH", str(broken.parent))
    env = {"ANDROID_HOME": str(tmp_path / "sdk"), "FAKE_ADB_STATE": str(tmp_path / "phone.json")}
    assert adb.find_adb(env) == sdk / "adb"


def test_override_wins(fake_adb):
    assert adb.find_adb({"WHATFERRY_ADB": str(fake_adb)}) == fake_adb


def no_sdk_anywhere(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(adb, "SDK_FOLDERS", ())
    monkeypatch.setattr(adb, "MISE_SDKS", str(tmp_path / "no-mise"))


def test_no_adb_anywhere(tmp_path, monkeypatch):
    no_sdk_anywhere(tmp_path, monkeypatch)
    assert adb.find_adb({}) is None


def test_devices_with_their_state(fake_adb):
    ready, waiting = adb.devices(fake_adb)
    assert (ready.serial, ready.model, ready.ready, ready.advice) == ("1A2B3C4D5E6F70", "Pixel 8 Pro", True, None)
    assert waiting.state == "unauthorized" and not waiting.ready
    assert "Allow" in waiting.advice


def test_backups_on_the_phone(fake_adb):
    backups = adb.phone_backups(fake_adb, "1A2B3C4D5E6F70")
    usable = [(b.app, b.account, b.name) for b in backups if b.usable]
    assert usable == [("WhatsApp", "1001", "msgstore.db.crypt15"),
                      ("WhatsApp Business", None, "msgstore.db.crypt15")]
    assert [b.usable for b in backups] == [True, True, False, False, False]
    old = next(b for b in backups if b.path.endswith("1002/Databases/msgstore.db.crypt14"))
    assert "rooted" in old.note and old.account == "1002"
    increment = next(b for b in backups if "increment" in b.name)
    assert "partial" in increment.note
    assert backups[0].local_name == "whatsapp-account-1001-msgstore.db.crypt15"
    assert backups[1].local_name == "whatsapp-business-msgstore.db.crypt15"


def test_pull_into_a_private_folder(fake_adb, tmp_path):
    remote = "/sdcard/Android/media/com.whatsapp/WhatsApp/accounts/1001/Databases/msgstore.db.crypt15"
    target = adb.pull(fake_adb, "1A2B3C4D5E6F70", remote, tmp_path / "out")
    assert target == tmp_path / "out" / "whatsapp-account-1001-msgstore.db.crypt15"
    assert target.read_bytes() == f"contents of {remote}".encode()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert not list(target.parent.glob(".*.part"))
    # Again: replaces the earlier copy.
    assert adb.pull(fake_adb, "1A2B3C4D5E6F70", remote, tmp_path / "out") == target


@pytest.mark.parametrize("remote", ["/sdcard/DCIM/Camera/IMG_0001.jpg", "/data/data/com.whatsapp/files/key",
                                    "/sdcard/Android/media/com.whatsapp/WhatsApp/accounts/1001/Databases/../../x"])
def test_pull_only_what_the_phone_listed(fake_adb, tmp_path, remote):
    with pytest.raises(adb.AdbError, match="isn't one of the phone's WhatsApp backups"):
        adb.pull(fake_adb, "1A2B3C4D5E6F70", remote, tmp_path / "out")
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir())


def test_cli_lists_the_phone(fake_adb, capsys):
    assert main(["android", "phone"]) == 0
    out = capsys.readouterr().out
    assert "Pixel 8 Pro (1A2B3C4D5E6F70): ready" in out
    assert "✓ msgstore.db.crypt15" in out and "account 1001" in out
    assert "tap Allow" in out


def test_cli_pulls_every_usable_full_backup(fake_adb, tmp_path, capsys):
    assert main(["android", "pull", "--serial", "1A2B3C4D5E6F70", "--to", str(tmp_path / "got")]) == 0
    assert sorted(p.name for p in (tmp_path / "got").iterdir()) == [
        "whatsapp-account-1001-msgstore.db.crypt15", "whatsapp-business-msgstore.db.crypt15"]


def test_cli_explains_a_missing_adb(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WHATFERRY_ADB", raising=False)
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT", "LOCALAPPDATA"):
        monkeypatch.delenv(var, raising=False)
    no_sdk_anywhere(tmp_path, monkeypatch)
    assert main(["android", "phone"]) == 1
    assert "platform-tools" in capsys.readouterr().err


def test_wizard_copies_from_the_phone(fake_adb, private_home):
    import threading

    from test_ui import request, run
    from whatferry.ui.server import Server
    from whatferry.ui.wizard import Wizard

    srv = Server(Wizard(private_home))
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    try:
        _, _, phone = request(srv, "GET", "/api/android/phone")
        ready = next(d for d in phone["devices"] if d["ready"])
        assert ready["backups"][0]["local_name"] == "whatsapp-account-1001-msgstore.db.crypt15"
        job = run(srv, "/api/android/phone/pull", {"serial": ready["serial"], "path": ready["backups"][0]["path"]})
        assert job["status"] == "done", job
        copied = Path(job["result"]["path"])
        assert copied.parent == Path.home() / "whatferry-android"
        # Search again finds the copy under its new name.
        _, _, found = request(srv, "GET", "/api/android/candidates")
        assert copied.name in [f["name"] for f in found["files"]]
        bad = run(srv, "/api/android/phone/pull", {"serial": ready["serial"], "path": "/sdcard/secret.txt"})
        assert bad["status"] == "error" and "isn't one of" in bad["error"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_fake_adb_answers_like_real_adb(fake_adb):
    assert adb._answers(fake_adb)
