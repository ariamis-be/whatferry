"""The harness without phones: kit, allow-list, codes, the runner's pauses and resumes, notifications."""

import json
import os
import sys
from pathlib import Path

import pytest

from harness import __main__ as cli
from harness import config, devices, otp, report, scenarios
from harness.config import KitError
from harness.report import Run
from harness.scenarios import Context, NeedsPerson, Step

KEY = "0123456789abcdef" * 4
SECRETS = f"""
backup_passphrase = "correct horse"
number_b = "+32 470 00 00 00"
iphone_udid = "00008160-0020"
android_serial = "PIXEL"

[notify]
ntfy = "https://ntfy.example/topic"
"""


@pytest.fixture
def secrets(tmp_path):
    path = tmp_path / "secrets.toml"
    path.write_text(SECRETS)
    path.chmod(0o600)
    return path


@pytest.fixture
def kit(secrets, tmp_path):
    return config.load(secrets, tmp_path / "kit-home")


# The kit

def test_kit_loads_and_never_prints_its_secrets(kit):
    assert kit.number_b == "+32 470 00 00 00" and kit.notify.ntfy == "https://ntfy.example/topic"
    assert kit.android_key is None
    assert "correct horse" not in repr(kit) and "correct horse" not in str(kit)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no file modes")
def test_a_secrets_file_others_can_read_is_refused(secrets):
    secrets.chmod(0o644)
    with pytest.raises(KitError, match="chmod 600"):
        config.load(secrets)


def test_missing_settings_and_a_bad_key_are_refused(secrets):
    secrets.write_text('backup_passphrase = "x"\n')
    with pytest.raises(KitError, match="lacks number_b, iphone_udid, android_serial"):
        config.load(secrets)
    secrets.write_text(SECRETS.replace("[notify]", 'android_key = "1234"\n[notify]'))
    with pytest.raises(KitError, match="64 characters"):
        config.load(secrets)
    secrets.write_text(SECRETS + 'colour = "red"\n')
    with pytest.raises(KitError, match="unknown \\[notify\\] settings: colour"):
        config.load(secrets)


def test_a_key_read_off_the_pixel_is_kept_in_the_secrets_file(kit, secrets):
    kit.save_android_key(KEY)
    again = config.load(secrets, kit.home)
    assert again.android_key == KEY and again.notify.ntfy  # the [notify] table survived
    kit.save_android_key("f" * 64)
    assert config.load(secrets, kit.home).android_key == "f" * 64
    assert secrets.read_text().count("android_key") == 1
    if sys.platform != "win32":
        assert secrets.stat().st_mode & 0o777 == 0o600
    with pytest.raises(KitError):
        kit.save_android_key("not a key")


def test_a_key_is_read_with_its_spaces_and_capitals(secrets):
    spaced = " ".join(KEY.upper()[i:i + 4] for i in range(0, 64, 4))
    secrets.write_text(SECRETS.replace("[notify]", f'android_key = "{spaced}"\n[notify]'))
    assert config.load(secrets).android_key == KEY


def test_whatferry_works_in_the_kits_own_folder(kit):
    env = {"WHATFERRY_BACKUP_ROOT": "/Users/someone/Library/MobileSync/Backup"}
    config.isolate(kit, env)
    assert env["WHATFERRY_HOME"] == str(kit.home / "whatferry")
    assert env["WHATFERRY_BACKUP_ROOT"] == str(kit.home / "whatferry" / "backups")
    assert env["WHATFERRY_BACKUP_PASSPHRASE"] == "correct horse"


# Only the kit's phones

def test_any_other_phone_stops_the_harness(kit):
    devices.check_allowed(kit, devices.Connected(["00008160-0020"], ["PIXEL"]))
    with pytest.raises(devices.DeviceError, match="isn't the test kit's.*SOMEONES"):
        devices.check_allowed(kit, devices.Connected(["00008160-0020", "SOMEONES"], ["PIXEL"]))
    with pytest.raises(devices.DeviceError, match="isn't the test kit's.*OTHER-PIXEL"):
        devices.check_allowed(kit, devices.Connected(["00008160-0020"], ["PIXEL", "OTHER-PIXEL"]))
    with pytest.raises(devices.DeviceError, match="test iPhone isn't connected"):
        devices.check_allowed(kit, devices.Connected([], ["PIXEL"]))
    with pytest.raises(devices.DeviceError, match="test Pixel"):
        devices.check_allowed(kit, devices.Connected(["00008160-0020"], []))


# WhatsApp's code, from the Pixel's inbox

INBOX = """Row: 0 address=WhatsApp, body=Your WhatsApp code: 482-913
Don't share this code with others, date=1761480060000
Row: 1 address=+3247000, body=see you at 123-456, date=1761480050000
Row: 2 address=WhatsApp, body=Your WhatsApp code: 111-222, date=1761470000000
"""


def test_the_newest_whatsapp_code_since_the_pause():
    sms = otp.parse_inbox(INBOX)
    assert [s.date_ms for s in sms] == [1761480060000, 1761480050000, 1761470000000]
    assert "share this code" in sms[0].body
    assert otp.whatsapp_code(sms, 1761480000000) == "482913"
    assert otp.whatsapp_code(sms, 1761480070000) is None
    assert otp.whatsapp_code(sms[1:], 0) == "111222"  # the friend's message with digits isn't WhatsApp's


def test_waiting_for_a_code():
    class Pixel:
        calls = 0

        def sms_inbox(self):
            Pixel.calls += 1
            return INBOX if Pixel.calls >= 3 else ""

    clock = iter(range(100))
    assert otp.wait_for_code(Pixel(), 1761480000000, timeout=50, sleep=lambda _: None,
                             clock=lambda: next(clock)) == "482913"
    assert Pixel.calls == 3
    never = type("Never", (), {"sms_inbox": lambda self: ""})()
    clock = iter(range(100))
    assert otp.wait_for_code(never, 0, timeout=5, sleep=lambda _: None, clock=lambda: next(clock)) is None


def test_the_key_is_read_off_the_screen():
    groups = [KEY[i:i + 4] for i in range(0, 64, 4)]
    one_view = f'<node text="{" ".join(groups)}" resource-id="x" bounds="[0,0][1,1]"/>'
    many_views = "".join(f'<node text="{g}" bounds="[0,0][1,1]"/>' for g in groups)
    assert scenarios.key_on_screen(one_view) == KEY
    assert scenarios.key_on_screen(many_views) == KEY
    assert scenarios.key_on_screen('<node text="Your 64-digit key"/>') is None


def test_b_is_typed_as_country_code_and_number():
    assert scenarios.split_number("+32 470 00 00 00") == ("32", "470000000")
    with pytest.raises(scenarios.StepFailed):
        scenarios.split_number("+32470000000")


# The runner: pauses, failures, resumes

class Phone:
    def __init__(self):
        self.shots = 0

    def screenshot(self, path: Path):
        self.shots += 1
        path.write_bytes(b"png")
        return path


@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(scenarios, "notify", lambda kit, title, message, **kw: messages.append((title, message)))
    return messages


def context(kit, tmp_path) -> Context:
    c = Context(kit, Run.new(kit.runs, "test", today="2026-11-01"), {"b_on": "android"})
    c._android, c._iphone = Phone(), Phone()
    return c


def test_a_manual_step_pauses_and_resume_goes_on(kit, tmp_path, sent):
    done = []
    steps = [Step("one", lambda c: done.append("one")),
             Step("tap", manual="Tap the thing."),
             Step("two", lambda c: done.append("two"))]
    c = context(kit, tmp_path)
    assert scenarios.execute(c, steps) == scenarios.PAUSED
    assert done == ["one"]
    assert c.run.state["status"] == "paused" and c.run.state["paused_at"] == "tap"
    assert sent[0][0] == "whatferry harness: your turn" and "Tap the thing." in sent[0][1]
    assert "harness resume" in sent[0][1]
    assert c._iphone.shots == 1

    resumed = Context(kit, Run(c.run.folder), {"b_on": "android"})
    resumed._android, resumed._iphone = Phone(), Phone()
    assert scenarios.execute(resumed, steps, resuming=True) == scenarios.PASSED
    assert done == ["one", "two"]  # "one" isn't run again
    assert resumed.run.steps["tap"]["by"] == "person"
    assert resumed.run.state["status"] == "passed"
    assert sent[-1][0] == "whatferry harness: passed"


def test_a_failure_stops_with_screenshots_and_resume_retries_it(kit, tmp_path, sent):
    attempts = []

    def flaky(c):
        attempts.append(1)
        if len(attempts) == 1:
            raise devices.FlowFailed("backup", "unknown screen: 'Try WhatsApp Plus'")

    steps = [Step("flaky", flaky), Step("after", lambda c: None)]
    c = context(kit, tmp_path)
    assert scenarios.execute(c, steps) == scenarios.FAILED
    assert c.run.steps["flaky"]["status"] == "failed" and "Try WhatsApp Plus" in c.run.steps["flaky"]["error"]
    assert c.run.state["summary"].startswith("failed at flaky")
    assert sorted(p.name for p in (c.run.folder / "screenshots").iterdir()) == ["01-flaky-pixel.png",
                                                                                "02-flaky-iphone.png"]
    assert sent[-1][0] == "whatferry harness: failed"
    assert scenarios.execute(c, steps, resuming=True) == scenarios.PASSED
    assert len(attempts) == 2


def test_a_step_that_needs_a_person_is_done_once_its_condition_holds(kit, tmp_path, sent):
    def read_key(c):
        raise NeedsPerson("Copy the key.")

    steps = [Step("key", read_key, done_when=lambda c: bool(c.kit.android_key)), Step("after", lambda c: None)]
    c = context(kit, tmp_path)
    assert scenarios.execute(c, steps) == scenarios.PAUSED
    assert "Copy the key." in sent[0][1]
    assert scenarios.execute(c, steps, resuming=True) == scenarios.PAUSED  # not done yet: asked again
    c.kit.android_key = KEY
    assert scenarios.execute(c, steps, resuming=True) == scenarios.PASSED


def test_while_paused_for_bs_code_it_is_sent_on(kit, tmp_path, sent):
    c = context(kit, tmp_path)
    steps = [Step("add_b", manual="Add B.", otp=True)]
    assert scenarios.execute(c, steps, wait_for_code=lambda android, since: "482913") == scenarios.PAUSED
    assert sent[-1] == ("whatferry harness: code for B", "WhatsApp's code for B: 482 913")


def test_roundtrip_starts_where_b_is():
    assert scenarios.steps_for("roundtrip", {"b_on": "android"})[1].name == "a2i.android_ready"
    assert scenarios.steps_for("roundtrip", {"b_on": "iphone"})[1].name == "i2a.ios_source"
    names = [s.name for s in scenarios.steps_for("roundtrip", {})]
    assert len(names) == len(set(names))  # one state entry per step


# Notifications

def test_ntfy_gets_the_title_and_the_line(kit, tmp_path):
    requests = []

    class Response:
        def close(self):
            pass

    def opener(request, timeout):
        requests.append(request)
        return Response()

    assert report.notify(kit, "whatferry harness: passed", "a2i 10 messages", opener=opener) == ["ntfy"]
    assert requests[0].full_url == "https://ntfy.example/topic"
    assert requests[0].get_header("Title") == "whatferry harness: passed"
    assert requests[0].data == b"a2i 10 messages"
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"\x89PNG")
    report.notify(kit, "t", "your turn", urgent=True, attach=shot, opener=opener)
    assert requests[1].data == b"\x89PNG" and requests[1].get_header("Priority") == "high"


def test_a_notification_that_cant_be_sent_never_stops_the_run(kit, capsys):
    def offline(request, timeout):
        raise OSError("no network")

    assert report.notify(kit, "t", "m", opener=offline) == []
    assert "no network" in capsys.readouterr().err


def test_mail(kit):
    kit.notify.ntfy = None
    kit.notify.mail_to, kit.notify.smtp_host, kit.notify.smtp_user = "me@example.com", "smtp.example", "me"
    sent_mail = []

    class SMTP:
        def __init__(self, host, port, timeout):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, message):
            sent_mail.append(message)

    assert report.notify(kit, "whatferry harness: failed", "failed at a2i.verify", smtp=SMTP) == ["mail"]
    assert sent_mail[0]["Subject"] == "whatferry harness: failed"


# The command line

def test_no_secrets_file_refuses(tmp_path, capsys):
    assert cli.main(["--secrets", str(tmp_path / "none.toml"), "status"]) == cli.REFUSED
    assert "no secrets file" in capsys.readouterr().err


def test_a_paused_run_must_be_resumed_or_abandoned(kit, secrets, monkeypatch, capsys):
    monkeypatch.setenv("WHATFERRY_HARNESS_HOME", str(kit.home))
    run = Run.new(kit.runs, "roundtrip")
    run.state.update(status="paused", paused_at="a2i.iphone_add_b")
    run.save()
    assert cli.main(["--secrets", str(secrets), "run"]) == cli.REFUSED
    assert "paused at a2i.iphone_add_b" in capsys.readouterr().err
    assert cli.main(["--secrets", str(secrets), "abandon"]) == 0
    assert json.loads((run.folder / "state.json").read_text())["status"] == "abandoned"


@pytest.mark.skipif(sys.platform == "win32", reason="a stale lock is removed by hand there")
def test_one_harness_at_a_time(kit):
    kit.home.mkdir(parents=True)
    (kit.home / "lock").write_text(str(os.getpid()))
    with pytest.raises(devices.DeviceError, match="another harness is running"):
        with cli._lock(kit):
            pass
    (kit.home / "lock").write_text("999999999")  # a harness that died: its lock is taken over
    with cli._lock(kit):
        assert (kit.home / "lock").read_text() == str(os.getpid())
    assert not (kit.home / "lock").exists()


def test_status_lists_the_steps(kit, secrets, monkeypatch, capsys):
    monkeypatch.setenv("WHATFERRY_HARNESS_HOME", str(kit.home))
    run = Run.new(kit.runs, "a2i")
    run.state["order"] = ["a2i.preflight", "a2i.iphone_remove_b"]
    run.mark("a2i.preflight", "done")
    run.mark("a2i.iphone_remove_b", "paused", instructions="Remove B.")
    assert cli.main(["--secrets", str(secrets), "status"]) == 0
    out = capsys.readouterr().out
    assert "done    a2i.preflight" in out and "paused  a2i.iphone_remove_b" in out and "Remove B." in out


