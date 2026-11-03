"""python -m harness run|resume|status|abandon|preflight|code|ios-check|spike

Exit codes: 0 passed, 1 failed, 2 refused to start, 75 paused for a person.
"""

import argparse
import asyncio
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from whatferry import iphone, restore

from harness import config, devices, ios_flows, ios_ui, otp, scenarios
from harness.report import Run

REFUSED = 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="harness", description="whatferry's monthly round trip on the test kit")
    p.add_argument("--secrets", type=Path, help="the kit's secrets file "
                   f"(default: $WHATFERRY_HARNESS_SECRETS or {config.DEFAULT_SECRETS})")
    commands = p.add_subparsers(dest="command", required=True, metavar="command")
    r = commands.add_parser("run", help="start a new run")
    r.add_argument("scenario", nargs="?", default="roundtrip", choices=sorted(scenarios.SCENARIOS))
    commands.add_parser("resume", help="continue the last run from the step that paused or failed")
    commands.add_parser("status", help="where the last run is")
    commands.add_parser("abandon", help="give up the last run, so a new one can start")
    commands.add_parser("preflight", help="check the kit: secrets, phones, versions")
    commands.add_parser("code", help="print the newest WhatsApp code on the Pixel (from the last 15 minutes)")
    commands.add_parser("ios-check", help="Stage 2: start WebDriverAgent on the iPhone, open WhatsApp, read one "
                                          "screen, take a screenshot; taps nothing")
    s = commands.add_parser("spike", help="Stage 2's go/no-go: ios-check, back up the iPhone, restore that same "
                                          "backup, then ios-check again with nobody touching the phone")
    s.add_argument("--yes", action="store_true", help="the restore replaces what's on the test iPhone with "
                                                      "the backup just made: confirm it")
    args = p.parse_args(argv)
    try:
        kit = config.load(args.secrets)
    except config.KitError as e:
        print(f"harness: {e}", file=sys.stderr)
        return REFUSED
    config.isolate(kit)
    try:
        return COMMANDS[args.command](kit, args)
    except (config.KitError, devices.DeviceError, scenarios.StepFailed, iphone.IphoneError) as e:
        print(f"harness: {e}", file=sys.stderr)
        return REFUSED


@contextmanager
def _lock(kit: config.Kit):
    """One harness at a time: a monthly timer firing while a run waits for a person must not start another."""
    kit.home.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = kit.home / "lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pid = path.read_text().strip()
        if pid.isdigit() and _alive(int(pid)):
            raise devices.DeviceError(f"another harness is running (pid {pid})") from None
        path.unlink(missing_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        # os.kill there ends the process instead of probing it: a stale lock is removed by hand.
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _run(kit, args) -> int:
    last = Run.latest(kit.runs)
    if last and last.state.get("status") in ("paused", "failed", "running"):
        print(f"harness: the run in {last.folder} is {last.state['status']} at "
              f"{last.state.get('paused_at') or _failed_at(last) or '?'}: `resume` it or `abandon` it",
              file=sys.stderr)
        return REFUSED
    with _lock(kit):
        devices.check_allowed(kit)
        state = scenarios.load_kit_state(kit)
        steps = scenarios.steps_for(args.scenario, state, kit.iphone_accounts)
        run = Run.new(kit.runs, args.scenario)
        run.log(f"run {args.scenario}, B on the {'Pixel' if state.get('b_on', 'android') == 'android' else 'iPhone'}")
        return scenarios.execute(scenarios.Context(kit, run, state), steps)


def _resume(kit, args) -> int:
    run = Run.latest(kit.runs)
    if not run or run.state.get("status") not in ("paused", "failed", "running"):
        print("harness: no run to resume", file=sys.stderr)
        return REFUSED
    with _lock(kit):
        devices.check_allowed(kit)
        state = scenarios.load_kit_state(kit)
        # The order the run started with: B's side has moved since, so it isn't recomputed.
        steps = scenarios.steps_for(run.state["scenario"], state, kit.iphone_accounts)
        by_name = {s.name: s for s in steps}
        order = run.state.get("order") or [s.name for s in steps]
        run.log("resume")
        return scenarios.execute(scenarios.Context(kit, run, state), [by_name[n] for n in order], resuming=True)


def _failed_at(run: Run) -> str | None:
    return next((n for n, s in run.steps.items() if s.get("status") == "failed"), None)


def _status(kit, args) -> int:
    run = Run.latest(kit.runs)
    if not run:
        print("No run yet.")
        return 0
    s = run.state
    print(f"{run.folder}: {s.get('scenario')} {s.get('status')}")
    for name in s.get("order", []):
        step = s.get("steps", {}).get(name, {})
        print(f"  {step.get('status', '-'):<7} {name}" + (f"  {step['error']}" if step.get("error") else ""))
        if step.get("status") == "paused":
            print(f"          {step.get('instructions')}")
    if s.get("summary"):
        print(s["summary"])
    return 0


def _abandon(kit, args) -> int:
    run = Run.latest(kit.runs)
    if run and run.state.get("status") in ("paused", "failed", "running"):
        run.finish("abandoned", f"abandoned at {run.state.get('paused_at') or _failed_at(run) or '?'}")
        print(f"Abandoned {run.folder}.")
    return 0


def _preflight(kit, args) -> int:
    devices.check_allowed(kit)
    android, phone = devices.Android(kit), devices.Iphone(kit)
    print(f"Kit: {kit!r}")
    print(f"  Pixel: WhatsApp {android.whatsapp_version() or '?'}")
    print(f"  iPhone: iOS {phone.phone().ios_version or '?'}, WhatsApp {phone.whatsapp_version() or '?'}")
    print(f"  B on the {'Pixel' if scenarios.load_kit_state(kit).get('b_on', 'android') == 'android' else 'iPhone'}")
    print(f"  64-digit key {'in' if kit.android_key else 'NOT in'} the secrets file")
    return 0


def _code(kit, args) -> int:
    since = int((time.time() - 900) * 1000)
    code = otp.whatsapp_code(otp.parse_inbox(devices.Android(kit).sms_inbox()), since)
    print(f"{code[:3]} {code[3:]}" if code else "No WhatsApp code in the last 15 minutes.")
    return 0 if code else 1


def _ios_check(kit, args) -> int:
    """WDA up, WhatsApp open, one screen read: steps 1 and 2 of the spike."""
    if not kit.ios_automation:
        print("harness: the secrets file has no [ios_automation] table (Stage 2 is off)", file=sys.stderr)
        return REFUSED
    devices.check_allowed(kit)
    kit.home.mkdir(parents=True, exist_ok=True, mode=0o700)
    shot = kit.home / "ios-check.png"
    automation = kit.ios_automation

    async def check() -> list[str]:
        async with ios_ui.session(kit.iphone_udid, automation.wda_app, automation.runner) as screen:
            await screen.launch(ios_flows.WHATSAPP)
            await asyncio.sleep(3)
            shot.write_bytes(await screen.screenshot())
            labels = [e.label for e in ios_ui.elements(await screen.source()) if e.label and e.visible]
            return labels

    try:
        labels = asyncio.run(check())
    except Exception as e:  # noqa: BLE001 - what failed is the answer
        print(f"Not working: {e}")
        return 1
    print(f"WebDriverAgent works: WhatsApp shows {len(labels)} labelled elements, "
          f"for example {', '.join(labels[:6]) or 'none'}")
    print(f"Screenshot: {shot}")
    return 0


def _spike(kit, args) -> int:
    """The plan's one-hour spike, scripted: does WDA come back after a restore with nobody touching the phone?"""
    if not args.yes:
        print("harness: the spike restores the test iPhone from a backup it makes first; run it with --yes",
              file=sys.stderr)
        return REFUSED
    with _lock(kit):
        print("1. Before the restore")
        if _ios_check(kit, args) != 0:
            return 1
        phone = devices.Iphone(kit)
        print("2. Backing up the iPhone (an hour for a full phone)")
        folder = iphone.backup(phone.phone(), kit.backup_passphrase)
        print("3. Restoring that same backup")
        restore.restore(folder, kit.backup_passphrase, lambda p: None)
        print("4. Waiting for the iPhone to restart")
        phone.wait_until_back()
        print("5. After the restore: Developer Mode, disk image and WebDriverAgent put back by the harness")
        result = _ios_check(kit, args)
    print("Go: Stage 2 can tap through a restore." if result == 0 else
          "No-go as it stands: see what failed above; Stage 1's pauses keep working meanwhile.")
    return result


COMMANDS = {"run": _run, "resume": _resume, "status": _status, "abandon": _abandon, "preflight": _preflight,
            "code": _code, "ios-check": _ios_check, "spike": _spike}

if __name__ == "__main__":
    sys.exit(main())
