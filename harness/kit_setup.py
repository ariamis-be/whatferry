"""Before the phones arrive, and every day after: set the kit up, say what it still lacks, run when it should.

`setup` writes the secrets file with what can be made without the phones (a
backup passphrase, a private ntfy topic) and, with `--detect`, fills in the
two phones' IDs once they are plugged in. `ready` lists every part of the kit
with what to do about the missing ones, phones or not. `watch` is what the
daily timer runs: a round trip whenever WhatsApp or iOS changed on either
phone since the last passing run, or when that run is a month old.
"""

import os
import re
import secrets as random
import shutil
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from whatferry import adb, iphone

from harness import config, devices
from harness.report import Run

# Phone fields `setup --detect` may fill: only while still empty.
_DETECT = {"iphone_udid": "iphones", "android_serial": "androids"}
# The tunnel pymobiledevice3's tunneld serves on, which Stage 2 needs on iOS 17 and later.
TUNNELD = ("127.0.0.1", 49151)
WATCH_MAX_AGE = timedelta(days=30)


def template(passphrase: str, topic: str) -> str:
    return f'''# The whatferry harness's test kit: harness/README.md says what each line is for.
# Readable by its owner only (chmod 600). Nothing in it is ever logged or reported.

# The test iPhone's backup passphrase. Made up by `harness setup`: on a phone that
# doesn't encrypt its backups yet, the first backup turns encryption on with it.
# If the phone already encrypts, put its passphrase here instead.
backup_passphrase = "{passphrase}"

# B, the number ferried between the phones, as typed into WhatsApp: "+<country code> <number>".
number_b = ""

# The only two phones the harness touches. Plug both in and run
# `python -m harness setup --detect` to fill them in.
iphone_udid = ""
android_serial = ""

# 2: B is added next to account A on the iPhone (two numbers).
# 1: B is the iPhone's only WhatsApp account (one SIM).
iphone_accounts = 2

# B's 64-digit end-to-end backup key, 0-9 and a-f. The harness writes it here
# itself when it reads one off the Pixel.
# android_key = ""

[notify]
# A private topic made by `harness setup`: subscribe to it in the ntfy app.
ntfy = "https://ntfy.sh/{topic}"
# Or mail, as well or instead:
# mail_to = "you@example.com"
# smtp_host = "smtp.example.com"
# smtp_user = ""
# smtp_password = ""

# Stage 2, the iPhone's taps without a person: harness/README.md, "Stage 2".
# [ios_automation]
# wda_app = "~/wda/build/Build/Products/Debug-iphoneos/WebDriverAgentRunner-Runner.app"
# runner = "com.facebook.WebDriverAgentRunner.xctrunner"
'''


def setup(path: Path, home: Path, *, detect: bool = False, connected=None) -> list[str]:
    """Write the secrets file if there is none; with detect, fill in empty phone IDs. Returns what it did."""
    done = []
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(template(random.token_urlsafe(24), f"whatferry-{random.token_hex(16)}"))
        done.append(f"wrote {path}")
    elif not detect:
        done.append(f"{path} is already there: left as it is (--detect fills in the phones)")
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    if detect:
        done += _detect(path, (connected or devices.connected)())
    return done


def _detect(path: Path, found: devices.Connected) -> list[str]:
    text, done = path.read_text(), []
    for key, side in _DETECT.items():
        line = re.search(rf'(?m)^{key}\s*=\s*"(.*)"\s*$', text)
        if line and line.group(1):
            done.append(f"{key} already set: left as it is")
            continue
        ids = getattr(found, side)
        if len(ids) != 1:
            what = "iPhone" if side == "iphones" else "Android phone (with USB debugging on)"
            done.append(f"{key}: {'no' if not ids else len(ids)} {what} connected; plug in exactly one")
            continue
        value = f'{key} = "{ids[0]}"'
        text = re.sub(rf"(?m)^{key}\s*=.*$", value, text) if line else text.replace("\n[", f"\n{value}\n\n[", 1)
        done.append(f"{key} = {ids[0]}")
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    tmp.chmod(0o600)
    os.replace(tmp, path)
    return done


@dataclass
class Item:
    name: str
    ok: bool | None  # None: optional, or can't be known yet
    detail: str


@dataclass
class Probes:
    """What `ready` asks the computer; tests stand in for each."""

    adb: Callable = adb.find_adb
    which: Callable = shutil.which
    connected: Callable = devices.connected
    iphones: Callable = iphone.iphones
    tunnel_up: Callable = None
    platform: str = sys.platform

    def __post_init__(self):
        self.tunnel_up = self.tunnel_up or _tunnel_up


def _tunnel_up() -> bool:
    try:
        socket.create_connection(TUNNELD, timeout=1).close()
        return True
    except OSError:
        return False


def ready(secrets: Path, home: Path, probes: Probes | None = None) -> list[Item]:
    """Every part of the kit, with what to do about each missing one. Works with no phone connected."""
    p = probes or Probes()
    items: list[Item] = []
    try:
        kit = config.load(secrets, home)
        items.append(Item("secrets file", True, str(kit.secrets)))
    except config.KitError as e:
        items.append(Item("secrets file", False, f"{e}; `python -m harness setup` writes one"))
        kit = None

    tool = p.adb()
    items.append(Item("adb", bool(tool), str(tool) if tool else
                      "not found: brew install --cask android-platform-tools, or sudo apt install adb"))
    maestro = p.which(kit.maestro if kit else "maestro") or p.which(str(Path("~/.maestro/bin/maestro").expanduser()))
    items.append(Item("Maestro", bool(maestro), maestro or
                      'not found: curl -fsSL "https://get.maestro.mobile.dev" | bash'))
    try:
        p.iphones()
        items.append(Item("usbmuxd", True, "reachable"))
    except iphone.IphoneError as e:
        items.append(Item("usbmuxd", False, f"{e}. Linux: sudo apt install usbmuxd"))

    if kit:
        items += _phones(kit, p, tool)
        n = kit.notify
        how = [w for w, on in (("ntfy", n.ntfy), ("mail", n.mail_to and n.smtp_host)) if on]
        items.append(Item("notifications", bool(how), ", ".join(how) + "; `python -m harness ping` sends a test"
                          if how else "set [notify] ntfy or mail in the secrets file"))
        items.append(Item("64-digit key", True if kit.android_key else None, "in the secrets file" if kit.android_key
                          else "not yet: the first iPhone → Android run reads it off the Pixel"))
        items += _stage2(kit, p)
        baseline = kit.home / "baseline.json"
        items.append(Item("baseline", True if baseline.is_file() else None, str(baseline) if baseline.is_file()
                          else "not yet: the first passing run records the seed corpus"))
    items.append(_timer(p.platform))
    return items


def _phones(kit: config.Kit, p: Probes, tool) -> list[Item]:
    found = p.connected()
    try:
        devices.check_allowed(kit, found)
    except devices.DeviceError as e:
        strangers = "isn't the test kit's" in str(e)
        return [Item("phones", False, str(e) + ("" if strangers or tool else "; adb is needed to see the Pixel"))]
    return [Item("phones", True, f"iPhone …{kit.iphone_udid[-6:]} and Pixel {kit.android_serial}, nothing else")]


def _stage2(kit: config.Kit, p: Probes) -> list[Item]:
    a = kit.ios_automation
    if not a:
        return [Item("Stage 2 (iPhone taps)", None, "off: every iPhone tap is a notified pause; see harness/README.md")]
    if not a.enabled:
        return [Item("Stage 2 (iPhone taps)", None, "turned off in the secrets file")]
    app = a.wda_app and a.wda_app.is_dir()
    items = [Item("WebDriverAgent", bool(app), str(a.wda_app) if app else
                  f"no signed WDA app at {a.wda_app or '(wda_app not set)'}: build it once, harness/README.md step 2")]
    up = p.tunnel_up()
    items.append(Item("tunneld", up, "running" if up else
                      "not running: install harness/schedule's tunneld service (it runs as root)"))
    return items


def _timer(platform: str) -> Item:
    if platform == "darwin":
        path = Path("~/Library/LaunchAgents/be.ariamis.whatferry-harness.plist").expanduser()
    elif platform.startswith("linux"):
        path = Path("~/.config/systemd/user/whatferry-harness.timer").expanduser()
    else:
        return Item("daily timer", None, "no timer for this system: run `python -m harness watch` daily yourself")
    return Item("daily timer", path.is_file(), str(path) if path.is_file()
                else f"not installed: see harness/schedule/ ({path.name})")


def show(items: list[Item]) -> int:
    marks = {True: "ok ", False: "NO ", None: "-  "}
    width = max(len(i.name) for i in items)
    for i in items:
        print(f"  {marks[i.ok]} {i.name:<{width}}  {i.detail}")
    missing = [i.name for i in items if i.ok is False]
    print(f"\nReady for `python -m harness run`." if not missing else f"\nStill to do: {', '.join(missing)}.")
    return 0 if not missing else 1


# --- watch -----------------------------------------------------------------------------------------------------


def last_pass(runs: Path) -> Run | None:
    folders = sorted((p for p in runs.glob("*") if (p / "state.json").is_file()),
                     key=lambda p: p.stat().st_mtime) if runs.is_dir() else []
    for folder in reversed(folders):
        run = Run(folder)
        if run.state.get("status") == "passed":
            return run
    return None


def why_run(versions: dict, last: Run | None, now: datetime | None = None) -> str | None:
    """Why the watch should start a round trip now, or None: nothing changed since a recent pass."""
    if last is None:
        return "no passing run yet"
    before = last.ctx.get("versions") or {}
    changed = [f"{k} {before.get(k) or '?'} → {v}" for k, v in sorted(versions.items()) if v and v != before.get(k)]
    if changed:
        return "changed since the last pass: " + ", ".join(changed)
    finished = last.state.get("finished") or last.state.get("started")
    try:
        when = datetime.fromisoformat(finished)
    except (TypeError, ValueError):
        return "the last pass has no date"
    now = now or datetime.now().astimezone()
    if now - when >= WATCH_MAX_AGE:
        return f"the last pass is from {when:%Y-%m-%d}"
    return None
