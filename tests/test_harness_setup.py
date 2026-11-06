"""The harness before its phones: setup, ready, ping and the daily watch, with stand-ins for every device."""

import os
import sys
from datetime import datetime, timedelta

import pytest

from harness import __main__ as cli
from harness import config, devices, kit_setup
from harness.report import Run
from whatferry import iphone

NONE = devices.Connected([], [])
KIT = devices.Connected(["00008160-0020"], ["PIXEL"])


def _filled(path):
    text = path.read_text().replace('number_b = ""', 'number_b = "+32 470 00 00 00"')
    path.write_text(text)


def test_setup_writes_a_private_secrets_file_that_names_what_is_missing(tmp_path):
    path = tmp_path / "conf" / "secrets.toml"
    done = kit_setup.setup(path, tmp_path / "home", connected=lambda: NONE)
    assert done == [f"wrote {path}"]
    if sys.platform != "win32":
        assert path.stat().st_mode & 0o777 == 0o600
    text = path.read_text()
    assert 'ntfy = "https://ntfy.sh/whatferry-' in text and "backup_passphrase = \"\"" not in text
    with pytest.raises(config.KitError, match="lacks number_b, iphone_udid, android_serial"):
        config.load(path, tmp_path / "home")


def test_setup_never_overwrites(tmp_path):
    path = tmp_path / "secrets.toml"
    kit_setup.setup(path, tmp_path / "home")
    before = path.read_text()
    assert "already there" in kit_setup.setup(path, tmp_path / "home")[0]
    assert path.read_text() == before


def test_detect_fills_the_one_phone_of_each_kind_then_the_kit_loads(tmp_path):
    path = tmp_path / "secrets.toml"
    kit_setup.setup(path, tmp_path / "home")
    _filled(path)
    done = kit_setup.setup(path, tmp_path / "home", detect=True, connected=lambda: KIT)
    assert done == ["iphone_udid = 00008160-0020", "android_serial = PIXEL"]
    kit = config.load(path, tmp_path / "home")
    assert (kit.iphone_udid, kit.android_serial, kit.iphone_accounts) == ("00008160-0020", "PIXEL", 2)
    if sys.platform != "win32":
        assert path.stat().st_mode & 0o777 == 0o600
    # Set once, never replaced by whatever is plugged in later.
    again = kit_setup.setup(path, tmp_path / "home", detect=True, connected=lambda: devices.Connected(["X"], ["Y"]))
    assert again == ["iphone_udid already set: left as it is", "android_serial already set: left as it is"]


def test_detect_refuses_to_guess_between_two_phones(tmp_path):
    path = tmp_path / "secrets.toml"
    kit_setup.setup(path, tmp_path / "home")
    done = kit_setup.setup(path, tmp_path / "home", detect=True,
                           connected=lambda: devices.Connected(["A", "B"], []))
    assert done[0] == "iphone_udid: 2 iPhone connected; plug in exactly one"
    assert done[1].startswith("android_serial: no Android phone")
    assert 'iphone_udid = ""' in path.read_text()


def _probes(**overrides):
    base = dict(adb=lambda: "/usr/bin/adb", which=lambda name: f"/bin/{name}", connected=lambda: KIT,
                iphones=lambda: [], tunnel_up=lambda: True, platform="other")
    return kit_setup.Probes(**(base | overrides))


def _by_name(items):
    return {i.name: i for i in items}


def test_ready_without_a_secrets_file_still_checks_the_tools(tmp_path):
    items = _by_name(kit_setup.ready(tmp_path / "missing.toml", tmp_path / "home", _probes(adb=lambda: None)))
    assert items["secrets file"].ok is False and "harness setup" in items["secrets file"].detail
    assert items["adb"].ok is False and items["Maestro"].ok is True and items["usbmuxd"].ok is True
    assert "phones" not in items


def test_ready_with_no_phones_says_which_is_missing(tmp_path):
    path = tmp_path / "secrets.toml"
    kit_setup.setup(path, tmp_path / "home")
    _filled(path)
    kit_setup.setup(path, tmp_path / "home", detect=True, connected=lambda: KIT)
    items = _by_name(kit_setup.ready(path, tmp_path / "home", _probes(connected=lambda: NONE)))
    assert items["phones"].ok is False and items["phones"].detail == "the test iPhone isn't connected"
    assert items["notifications"].ok is True and items["64-digit key"].ok is None
    assert items["Stage 2 (iPhone taps)"].ok is None and items["baseline"].ok is None


def test_ready_all_there(tmp_path, capsys):
    path = tmp_path / "secrets.toml"
    kit_setup.setup(path, tmp_path / "home")
    _filled(path)
    kit_setup.setup(path, tmp_path / "home", detect=True, connected=lambda: KIT)
    items = kit_setup.ready(path, tmp_path / "home", _probes())
    assert kit_setup.show(items) == 0
    assert "Ready for `python -m harness run`." in capsys.readouterr().out


def test_ready_stage2_needs_the_wda_app_and_the_tunnel(tmp_path):
    path = tmp_path / "secrets.toml"
    kit_setup.setup(path, tmp_path / "home")
    _filled(path)
    kit_setup.setup(path, tmp_path / "home", detect=True, connected=lambda: KIT)
    with path.open("a") as f:
        f.write(f'\n[ios_automation]\nwda_app = "{(tmp_path / "WDA.app").as_posix()}"\n')
    items = _by_name(kit_setup.ready(path, tmp_path / "home", _probes(tunnel_up=lambda: False)))
    assert items["WebDriverAgent"].ok is False and items["tunneld"].ok is False
    (tmp_path / "WDA.app").mkdir()
    items = _by_name(kit_setup.ready(path, tmp_path / "home", _probes()))
    assert items["WebDriverAgent"].ok is True and items["tunneld"].ok is True


def test_ready_reports_usbmuxd_missing(tmp_path):
    def gone():
        raise iphone.IphoneError("can't reach usbmuxd")

    items = _by_name(kit_setup.ready(tmp_path / "missing.toml", tmp_path / "home", _probes(iphones=gone)))
    assert items["usbmuxd"].ok is False and "usbmuxd" in items["usbmuxd"].detail


@pytest.mark.parametrize("platform, name", [("darwin", "be.ariamis.whatferry-harness.plist"),
                                             ("linux", "whatferry-harness.timer")])
def test_ready_looks_for_the_timer_where_the_system_keeps_it(tmp_path, monkeypatch, platform, name):
    monkeypatch.setenv("HOME", str(tmp_path))
    item = kit_setup._timer(platform)
    assert item.ok is False and name in item.detail


# --- watch -------------------------------------------------------------------------------------------------


VERSIONS = {"whatsapp_android": "2.26.41", "whatsapp_iphone": "26.40.1", "ios": "27.0.1"}
NOW = datetime(2026, 11, 7, 3, 0).astimezone()


def _passed(runs, versions, finished, name="2026-11-01"):
    run = Run.new(runs, "roundtrip", today=name)
    run.ctx["versions"] = dict(versions)
    run.finish("passed", "passed")
    run.state["finished"] = finished.isoformat()
    run.save()
    return run


def test_watch_runs_first_when_nothing_ever_passed():
    assert kit_setup.why_run(VERSIONS, None, NOW) == "no passing run yet"


def test_watch_runs_when_whatsapp_updates_on_either_phone(tmp_path):
    last = _passed(tmp_path / "runs", VERSIONS, NOW - timedelta(days=2))
    assert kit_setup.why_run(VERSIONS, last, NOW) is None
    newer = VERSIONS | {"whatsapp_iphone": "26.41.0"}
    assert kit_setup.why_run(newer, last, NOW) == "changed since the last pass: whatsapp_iphone 26.40.1 → 26.41.0"


def test_watch_runs_a_month_after_the_last_pass(tmp_path):
    last = _passed(tmp_path / "runs", VERSIONS, NOW - timedelta(days=30))
    assert kit_setup.why_run(VERSIONS, last, NOW) == "the last pass is from 2026-10-08"


def test_watch_ignores_a_version_it_couldnt_read(tmp_path):
    last = _passed(tmp_path / "runs", VERSIONS, NOW - timedelta(days=1))
    assert kit_setup.why_run(VERSIONS | {"ios": None}, last, NOW) is None


def test_last_pass_skips_failed_and_abandoned_runs(tmp_path):
    runs = tmp_path / "runs"
    good = _passed(runs, VERSIONS, NOW - timedelta(days=3))
    failed = Run.new(runs, "roundtrip", today="2026-11-05")
    failed.finish("failed", "failed at a2i_verify")
    later = good.folder.stat().st_mtime + 10
    os.utime(failed.state_path, (later, later))
    assert kit_setup.last_pass(runs).folder == good.folder


def _cli_kit(tmp_path, monkeypatch):
    path = tmp_path / "secrets.toml"
    kit_setup.setup(path, tmp_path / "home")
    _filled(path)
    kit_setup.setup(path, tmp_path / "home", detect=True, connected=lambda: KIT)
    monkeypatch.setenv("WHATFERRY_HARNESS_SECRETS", str(path))
    monkeypatch.setenv("WHATFERRY_HARNESS_HOME", str(tmp_path / "home"))
    for name in ("WHATFERRY_HOME", "WHATFERRY_BACKUP_ROOT", "WHATFERRY_BACKUP_PASSPHRASE", "WHATFERRY_ANDROID_KEY"):
        monkeypatch.delenv(name, raising=False)
    return path


def test_watch_waits_quietly_on_a_paused_run(tmp_path, monkeypatch, capsys):
    _cli_kit(tmp_path, monkeypatch)
    run = Run.new(tmp_path / "home" / "runs", "roundtrip")
    run.state.update(status="paused", paused_at="a2i_ios_add_b")
    run.save()
    monkeypatch.setattr(devices, "check_allowed", lambda kit: pytest.fail("no phone is touched while waiting"))
    assert cli.main(["watch"]) == 0
    assert "Waiting on" in capsys.readouterr().out


def test_watch_dry_run_says_why_and_starts_nothing(tmp_path, monkeypatch, capsys):
    _cli_kit(tmp_path, monkeypatch)
    monkeypatch.setattr(devices, "check_allowed", lambda kit: None)
    monkeypatch.setattr(devices.Android, "__init__", lambda self, kit: None)
    monkeypatch.setattr(devices.Android, "whatsapp_version", lambda self: "2.26.41")
    monkeypatch.setattr(devices.Iphone, "whatsapp_version", lambda self: "26.40.1")
    monkeypatch.setattr(devices.Iphone, "phone", lambda self: iphone.Iphone("00008160-0020", "Test iPhone",
                                                                            "27.0.1", True, False))
    monkeypatch.setattr(cli, "_run", lambda kit, args: pytest.fail("a dry run starts nothing"))
    assert cli.main(["watch", "--dry-run"]) == 0
    assert capsys.readouterr().out.strip() == "Would run: no passing run yet."


def test_setup_and_ready_work_before_any_secrets_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "conf" / "secrets.toml"
    monkeypatch.setenv("WHATFERRY_HARNESS_SECRETS", str(path))
    monkeypatch.setenv("WHATFERRY_HARNESS_HOME", str(tmp_path / "home"))
    probes = _probes(connected=lambda: NONE)
    monkeypatch.setattr(kit_setup, "Probes", lambda: probes)
    assert cli.main(["ready"]) == 1
    assert "Still to do: secrets file." in capsys.readouterr().out
    assert cli.main(["setup"]) == 0
    assert path.is_file() and "only phones" not in capsys.readouterr().out
    _filled(path)
    monkeypatch.setattr(devices, "connected", lambda: KIT)
    assert cli.main(["setup", "--detect"]) == 0
    out = capsys.readouterr().out
    assert "android_serial = PIXEL" in out and "clears WhatsApp on them" in out


def test_ping_sends_a_test_notification(tmp_path, monkeypatch, capsys):
    _cli_kit(tmp_path, monkeypatch)
    seen = []
    monkeypatch.setattr(cli.report, "notify", lambda kit, title, message: seen.append(title) or ["ntfy"])
    assert cli.main(["ping"]) == 0
    assert seen == ["whatferry harness: test"] and "Sent by ntfy." in capsys.readouterr().out


def test_the_timers_run_the_watch_daily():
    schedule = cli.Path(cli.__file__).parent / "schedule"
    assert "python -m harness watch" in (schedule / "be.ariamis.whatferry-harness.plist").read_text()
    assert "python -m harness watch" in (schedule / "whatferry-harness.service").read_text()
    assert "OnCalendar=*-*-* 03:00:00" in (schedule / "whatferry-harness.timer").read_text()
