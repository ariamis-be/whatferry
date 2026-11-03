"""The transfers, as steps: a2i (Android -> iPhone), i2a (iPhone -> Android), and roundtrip.

Each step is idempotent and its outcome lands in the run's state.json, so
`harness resume` picks up at the step that paused or failed. Stage 1: every
tap on the iPhone is a manual step. The harness takes a screenshot where it
can, sends a notification saying what to do, and stops; `resume` takes the
step as done and goes on. Anything it doesn't recognise (a flow that fails,
a database whose layout changed) stops the run the same way, never guessed.

B, the ferried number, ends each transfer on the other phone; kit.json in
the harness folder records where, so a roundtrip always starts with the
direction B's side calls for.
"""

import asyncio
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from whatferry import (android, android_writer, backup_writer, convert, ios, ios_backup, iphone, restore, schema,
                       to_android)
from whatferry.cli import SCHEMA_USES
from whatferry.ios_backup import Backup

from harness import devices, ios_flows, ios_ui, oracle, otp
from harness.config import Kit
from harness.report import Run, notify

PAUSED, FAILED, PASSED = 75, 1, 0
# WhatsApp shows the key as 16 groups of four hexadecimal characters.
_KEY_ON_SCREEN = re.compile(r"(?<![0-9a-f])((?:[0-9a-f]{4}\s*){15}[0-9a-f]{4})(?![0-9a-f])", re.I)


class Paused(Exception):
    pass


class StepFailed(Exception):
    pass


class NeedsPerson(Exception):
    """An automated step met something only a person can do; the step runs again on resume unless done_when says so."""


@dataclass
class Step:
    name: str
    run: Callable[["Context"], None] | None = None
    # A manual step (Stage 1): what the person does on the phone.
    manual: str | None = None
    # While paused at it, read B's code off the Pixel and send it on.
    otp: bool = False
    # For an automated step that may hand over to a person: what makes it done anyway on resume.
    done_when: Callable[["Context"], bool] | None = None
    # Stage 2: the manual step as taps, async (screen, context[, wait_for_code]); a failure falls back to the pause.
    auto: Callable | None = None


@dataclass
class Context:
    kit: Kit
    run: Run
    kit_state: dict = field(default_factory=dict)
    _android: devices.Android | None = None
    _iphone: devices.Iphone | None = None

    @property
    def android(self) -> devices.Android:
        if self._android is None:
            self._android = devices.Android(self.kit)
        return self._android

    @property
    def iphone(self) -> devices.Iphone:
        if self._iphone is None:
            self._iphone = devices.Iphone(self.kit)
        return self._iphone

    @property
    def ctx(self) -> dict:
        return self.run.ctx

    def save(self) -> None:
        self.run.save()
        save_kit_state(self.kit, self.kit_state)

    def log(self, message: str) -> None:
        self.run.log(message)

    def flow(self, name: str, **env: str) -> None:
        self.log(f"flow {name}")
        self.android.flow(name, self.run.path("maestro.log"), **env)

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)

    def phone_env(self) -> dict:
        country, number = split_number(self.kit.number_b)
        return {"COUNTRY_CODE": country, "PHONE": number}


def split_number(number: str) -> tuple[str, str]:
    """"+32 470 00 00 00" -> ("32", "470000000"): the country code ends at the first space, as the kit writes it."""
    head, _, rest = number.strip().lstrip("+").partition(" ")
    if not head.isdigit() or not re.sub(r"\D", "", rest):
        raise StepFailed("number_b must be written '+<country code> <number>', with a space after the country code")
    return head, re.sub(r"\D", "", rest)


# Kit state: where B is, and the cached Android template per WhatsApp version.

def load_kit_state(kit: Kit) -> dict:
    path = kit.home / "kit.json"
    return json.loads(path.read_text()) if path.is_file() else {"b_on": "android", "templates": {}}


def save_kit_state(kit: Kit, state: dict) -> None:
    kit.home.mkdir(parents=True, exist_ok=True, mode=0o700)
    (kit.home / "kit.json").write_text(json.dumps(state, indent=2))


# Steps shared by both directions

def preflight(c: Context) -> None:
    devices.check_allowed(c.kit)
    versions = {"whatsapp_android": c.android.whatsapp_version(), "whatsapp_iphone": c.iphone.whatsapp_version(),
                "ios": c.iphone.phone().ios_version}
    c.ctx.setdefault("versions", {}).update(versions)
    c.log("versions: " + ", ".join(f"{k} {v or '?'}" for k, v in versions.items()))
    if c.kit.taps_iphone:
        # Stage 2's needs, logged: a gap only turns its taps back into pauses, never stops the run.
        try:
            facts = asyncio.run(ios_ui.facts(c.kit.iphone_udid))
        except Exception as e:  # noqa: BLE001
            facts = {"error": str(e)}
        c.ctx["ios_automation"] = facts
        c.log("iPhone taps: " + ", ".join(f"{k} {v}" for k, v in facts.items()))
        if facts.get("supervised") is False:
            c.log("  not supervised: the panes after a restore will need a person (harness/README.md)")


def check_schema(c: Context, db: Path, label: str) -> None:
    """whatferry's schema check on a database the run is about to use; a STOP change ends the run here."""
    snap = schema.capture(db)
    found, worst = [], schema.HARMLESS
    for direction, uses, writes in SCHEMA_USES[snap["kind"]]:
        closest, changes = schema.closest(snap, uses, set(uses) if writes else set())
        found.append({"direction": direction, "closest": closest and closest["fingerprint"],
                      "changes": [{"level": ch.level, "what": ch.what} for ch in changes]})
        for ch in changes:
            if ch.level == schema.STOP or (ch.level == schema.REVIEW and worst == schema.HARMLESS):
                worst = ch.level
    c.run.save_json(f"compat/{label}-schema.json", {"fingerprint": schema.fingerprint(snap), "checks": found})
    c.log(f"schema {label}: {schema.fingerprint(snap)}, worst change: {worst}")
    if worst == schema.STOP:
        raise StepFailed(f"WhatsApp's {snap['kind']} database layout changed in a way whatferry refuses "
                         f"(compat/{label}-schema.json): capture it as schemas/CHANGES.md says")


def _key(c: Context):
    if not c.kit.android_key:
        raise StepFailed("the secrets file has no android_key: the Pixel's 64-digit backup key")
    return android.parse_key(c.kit.android_key)


def _pull_and_fingerprint(c: Context, prefix: str, label: str) -> tuple[Path, Path, dict]:
    """Back up WhatsApp on the Pixel, copy the backup and the media off, decrypt it, fingerprint it."""
    c.flow("backup")
    pulled = c.android.pull_backup(c.run.path(prefix, "android", "x").parent)
    _, inspected = android.inspect(pulled, _key(c))
    db = inspected / "msgstore.db"
    media = c.android.pull_media(c.run.path(prefix, "android-media", "x").parent)
    check_schema(c, db, f"{prefix}-{label}")
    fingerprint = oracle.android(db, media)
    oracle.save(fingerprint, c.run.path("fingerprints", f"{prefix}-{label}.json"))
    return db, media, fingerprint


def _verdict(c: Context, prefix: str, seed: dict, result: dict) -> None:
    d = oracle.diff(seed, result)
    c.run.save_json(f"{prefix}-diff.json", d)
    c.ctx[f"{prefix}.verdict"] = {"passed": d["passed"], "summary": oracle.summary(d)}
    baseline = c.kit.home / "baseline.json"
    if baseline.is_file():
        # Slow drift: what the very first seed had that this result no longer has.
        drift = oracle.diff(oracle.load(baseline), result)
        c.ctx[f"{prefix}.drift"] = drift["missing"]
    c.log(f"{prefix}: {oracle.summary(d)}")
    if not d["passed"]:
        raise StepFailed(f"{prefix}: {oracle.summary(d)} (see {prefix}-diff.json)")


def _seed(c: Context, prefix: str, fingerprint: dict) -> None:
    oracle.save(fingerprint, c.run.path("fingerprints", f"{prefix}-seed.json"))
    c.ctx[f"{prefix}.seed"] = str(c.run.path("fingerprints", f"{prefix}-seed.json"))
    baseline = c.kit.home / "baseline.json"
    if not baseline.is_file():
        oracle.save(fingerprint, baseline)


def _backup(c: Context, *, whatsapp_only: bool = False) -> Path:
    phone = c.iphone.phone()
    c.log(f"iPhone backup{' (WhatsApp only)' if whatsapp_only else ''}")
    last = [-10.0]

    def progress(p: float) -> None:
        if p >= last[0] + 25:
            last[0] = p
            c.log(f"  {p:.0f}%")

    return iphone.backup(phone, c.kit.backup_passphrase, whatsapp_only=whatsapp_only, progress=progress)


def _account_db(report: ios.Report, folder: str | None) -> Path:
    path = f"{folder}/{ios.CHAT_STORAGE}" if folder else ios.CHAT_STORAGE
    for db in report.databases:
        if db.domain == ios.SHARED_DOMAIN and db.path == path:
            return Path(db.extracted_to)
    raise StepFailed(f"the iPhone backup has no {path}")


# Android -> iPhone

def a2i_android_ready(c: Context) -> None:
    c.android.open_whatsapp()
    try:
        c.flow("home")
    except devices.FlowFailed:
        c.log("B isn't registered on the Pixel: registering")
        c.flow("register", **c.phone_env())
        c.flow("home")


def a2i_android_backup(c: Context) -> None:
    db, media, fingerprint = _pull_and_fingerprint(c, "a2i", "android")
    c.ctx.update({"a2i.android_db": str(db), "a2i.media": str(media)})
    _seed(c, "a2i", fingerprint)


def a2i_ios_before(c: Context) -> None:
    folder = _backup(c)
    index = ios_backup.snapshot_manifest(folder, c.run.path("a2i", "ios-before-index", "x").parent)
    c.ctx["a2i.before_index"] = str(index)


def a2i_ios_after(c: Context) -> None:
    folder = _backup(c)
    passphrase = c.kit.backup_passphrase
    after = Backup(folder, passphrase)
    report, _ = ios.inspect(after)
    if c.kit.iphone_accounts == 1:
        # B is WhatsApp's only, main account: its database is the one at the root.
        ends = re.sub(r"\D", "", c.kit.number_b)[-4:]
        main = next((a for a in report.accounts if a.main), None)
        if main is None or main.number_ends != ends:
            raise StepFailed("the iPhone's WhatsApp isn't set up as B: was B registered after the reinstall?")
        account = None
    else:
        # B is the account adding it created: its data/<id> folder is new since the "before" backup.
        d = ios.diff(Backup(Path(c.ctx["a2i.before_index"]), passphrase), after)
        new = sorted({e.path.rsplit("/", 1)[0] for e in d.added
                      if e.domain == ios.SHARED_DOMAIN and e.path.endswith(f"/{ios.CHAT_STORAGE}")})
        if len(new) != 1:
            raise StepFailed(f"expected one new account database after adding B, found {len(new)}: was B added?")
        account = new[0]
    ios_db = _account_db(report, account)
    check_schema(c, ios_db, "a2i-iphone")
    converted, convert_run = convert.convert(Path(c.ctx["a2i.android_db"]), ios_db, Path(c.ctx["a2i.media"]), account)
    c.run.save_json("compat/a2i-convert.json", converted.as_dict())
    problems = {k: v for k, v in converted.checks.items() if isinstance(v, int) and v and k not in ("messages", "chats")}
    if problems or converted.checks["integrity"] != "ok":
        raise StepFailed(f"the conversion's own checks failed: {problems or converted.checks['integrity']}")
    written_report, written = backup_writer.write_conversion(folder, passphrase, convert_run, account)
    c.run.save_json("compat/a2i-write.json", written_report.as_dict())
    c.ctx.update({"a2i.account": account, "a2i.written": str(written)})


def a2i_ios_restore(c: Context) -> None:
    folder = Path(c.ctx["a2i.written"])
    c.log("restoring onto the iPhone")
    restore.restore(folder, c.kit.backup_passphrase, lambda p: None)
    c.log("waiting for the iPhone to restart")
    c.iphone.wait_until_back()


def a2i_verify(c: Context) -> None:
    folder = _backup(c, whatsapp_only=True)
    backup = Backup(folder, c.kit.backup_passphrase)
    report, _ = ios.inspect(backup)
    account = c.ctx["a2i.account"]
    result = oracle.ios(_account_db(report, account), to_android.backup_media(backup, account))
    oracle.save(result, c.run.path("fingerprints", "a2i-iphone.json"))
    c.kit_state["b_on"] = "iphone"
    _verdict(c, "a2i", oracle.load(Path(c.ctx["a2i.seed"])), result)


A2I = [
    Step("a2i.preflight", preflight),
    Step("a2i.android_ready", a2i_android_ready),
    Step("a2i.android_backup", a2i_android_backup),
    Step("a2i.iphone_remove_b", manual=(
        "On the test iPhone, in WhatsApp: Settings → Accounts → B → Remove account, and delete its data from "
        "this iPhone, so B comes back with a fresh, empty database."), auto=ios_flows.remove_b),
    Step("a2i.ios_before", a2i_ios_before),
    Step("a2i.iphone_add_b", manual=(
        "On the test iPhone, in WhatsApp: Settings → Add account → B's number. The code goes to B's SIM in the "
        "Pixel: the harness sends it in a second notification. Wait until B's empty chat list shows."), otp=True,
        auto=ios_flows.add_b),
    Step("a2i.ios_after", a2i_ios_after),
    Step("a2i.ios_restore", a2i_ios_restore),
    Step("a2i.iphone_after_restore", manual=(
        "On the test iPhone: get past the panes after the restore (Restore Completed, the Apple Account "
        "sign-in), open WhatsApp, switch to B, and wait until its chats show."), auto=ios_flows.after_restore),
    Step("a2i.verify", a2i_verify),
]


def a2i_iphone_remove_whatsapp(c: Context) -> None:
    """One-account kit: WhatsApp and all its data off the iPhone, so B starts as on an iPhone that never had it."""
    if c.iphone.has_app(ios_flows.WHATSAPP):
        c.log("removing WhatsApp from the iPhone")
        c.iphone.remove_app(ios_flows.WHATSAPP)


# The one-account kit: no A, B the iPhone's only WhatsApp account. No "before"
# backup either: it only served to find a second account's new folder.
A2I_ONE_ACCOUNT = [
    Step("a2i.preflight", preflight),
    Step("a2i.android_ready", a2i_android_ready),
    Step("a2i.android_backup", a2i_android_backup),
    Step("a2i.iphone_remove_whatsapp", a2i_iphone_remove_whatsapp),
    Step("a2i.iphone_reinstall_whatsapp", manual=(
        "On the test iPhone: App Store → WhatsApp → download it again (the harness removed it, with its data)."),
        auto=ios_flows.reinstall_whatsapp,
        done_when=lambda c: c.iphone.has_app(ios_flows.WHATSAPP)),
    Step("a2i.iphone_register_b", manual=(
        "On the test iPhone: open WhatsApp and set it up with B's number. The code goes to B's SIM in the Pixel: "
        "the harness sends it in a second notification. Skip restoring from iCloud. Wait until B's empty chat "
        "list shows."), otp=True, auto=ios_flows.register_b),
    Step("a2i.ios_after", a2i_ios_after),
    Step("a2i.ios_restore", a2i_ios_restore),
    Step("a2i.iphone_after_restore", manual=(
        "On the test iPhone: get past the panes after the restore (Restore Completed, the Apple Account "
        "sign-in), open WhatsApp, and wait until B's chats show."), auto=ios_flows.after_restore),
    Step("a2i.verify", a2i_verify),
]


# iPhone -> Android

def i2a_ios_source(c: Context) -> None:
    folder = _backup(c, whatsapp_only=True)
    backup = Backup(folder, c.kit.backup_passphrase)
    report, _ = ios.inspect(backup)
    ends = re.sub(r"\D", "", c.kit.number_b)[-4:]
    accounts = [a for a in report.accounts if a.number_ends == ends]
    if not accounts:
        raise StepFailed("B isn't among the iPhone's WhatsApp accounts: is it registered there?")
    account = accounts[0].folder
    ios_db = _account_db(report, account)
    check_schema(c, ios_db, "i2a-iphone")
    c.ctx.update({"i2a.backup": str(folder), "i2a.account": account, "i2a.ios_db": str(ios_db)})
    _seed(c, "i2a", oracle.ios(ios_db, to_android.backup_media(backup, account)))


def _template(c: Context) -> Path:
    return c.kit.home / "templates" / (c.ctx["i2a.whatsapp"] or "unknown")


def _template_cached(c: Context) -> bool:
    return (_template(c) / "msgstore.db.crypt15").is_file() and bool(c.kit.android_key)


def i2a_template_register(c: Context) -> None:
    """An empty B account on the Pixel, whose backup is the template the iPhone's chats go into."""
    c.ctx["i2a.whatsapp"] = c.android.whatsapp_version()
    if _template_cached(c):
        c.log(f"template for WhatsApp {c.ctx['i2a.whatsapp']} cached")
        return
    c.android.clear_whatsapp()
    c.android.open_whatsapp()
    c.flow("register", **c.phone_env())
    c.flow("home")


def i2a_template_key(c: Context) -> None:
    if _template_cached(c):
        return
    c.flow("enable_key")
    key = key_on_screen(c.android.screen_text())
    if not key:
        raise NeedsPerson("The Pixel shows WhatsApp's 64-digit backup key, which the harness couldn't read: put it "
                          f"in {c.kit.secrets} as android_key = \"<the 64 characters>\", then on the Pixel tap "
                          "through until the key is confirmed, and resume.")
    c.kit.save_android_key(key)
    c.flow("confirm_key")


def key_on_screen(dump: str) -> str | None:
    """The 64-digit key in a uiautomator dump, whether one view holds it or each group has its own."""
    texts = " ".join(re.findall(r'text="([^"]*)"', dump))
    found = _KEY_ON_SCREEN.search(texts) or _KEY_ON_SCREEN.search(dump)
    return re.sub(r"\s", "", found.group(1)).lower() if found else None


def i2a_template_backup(c: Context) -> None:
    if _template_cached(c):
        return
    c.flow("backup")
    template = _template(c)
    pulled = c.android.pull_backup(template)
    pulled.rename(template / "msgstore.db.crypt15")
    c.kit_state.setdefault("templates", {})[c.ctx["i2a.whatsapp"] or "unknown"] = str(template)


def i2a_android_convert(c: Context) -> None:
    template = _template(c) / "msgstore.db.crypt15"
    key = _key(c)
    _, inspected = android.inspect(template, key)
    check_schema(c, inspected / "msgstore.db", "i2a-template")
    backup = Backup(Path(c.ctx["i2a.backup"]), c.kit.backup_passphrase)
    account = c.ctx["i2a.account"]
    converted, convert_run = to_android.convert(Path(c.ctx["i2a.ios_db"]), inspected / "msgstore.db",
                                                to_android.backup_media(backup, account), account,
                                                c.ctx["i2a.whatsapp"])
    c.run.save_json("compat/i2a-convert.json", converted.as_dict())
    written_report, folder = android_writer.write_backup(template, key, convert_run)
    c.run.save_json("compat/i2a-write.json", written_report.as_dict())
    c.ctx["i2a.written"] = str(folder)


def i2a_android_restore(c: Context) -> None:
    c.android.clear_whatsapp()
    c.android.push(Path(c.ctx["i2a.written"]))
    c.android.open_whatsapp()
    # restore.yaml registers B first, stopping at the restore screen instead of skipping it.
    c.flow("restore", KEY=c.kit.android_key or "", **c.phone_env())
    c.flow("home")


def i2a_verify(c: Context) -> None:
    _, _, result = _pull_and_fingerprint(c, "i2a", "android")
    c.kit_state["b_on"] = "android"
    _verdict(c, "i2a", oracle.load(Path(c.ctx["i2a.seed"])), result)


I2A = [
    Step("i2a.preflight", preflight),
    Step("i2a.ios_source", i2a_ios_source),
    Step("i2a.template_register", i2a_template_register),
    Step("i2a.template_key", i2a_template_key, done_when=lambda c: bool(c.kit.android_key)),
    Step("i2a.template_backup", i2a_template_backup),
    Step("i2a.android_convert", i2a_android_convert),
    Step("i2a.android_restore", i2a_android_restore),
    Step("i2a.verify", i2a_verify),
]

SCENARIOS = ("a2i", "i2a", "roundtrip")


def steps_for(scenario: str, kit_state: dict, accounts: int = 2) -> list[Step]:
    """The scenario's steps for a kit whose iPhone has `accounts` WhatsApp accounts (B next to A, or B alone)."""
    if scenario not in SCENARIOS:
        raise StepFailed(f"unknown scenario {scenario!r}: one of {', '.join(SCENARIOS)}")
    a2i = A2I_ONE_ACCOUNT if accounts == 1 else A2I
    if scenario == "a2i":
        return a2i
    if scenario == "i2a":
        return I2A
    return a2i + I2A if kit_state.get("b_on", "android") == "android" else I2A + a2i


def execute(c: Context, steps: list[Step], *, resuming: bool = False, wait_for_code=otp.wait_for_code) -> int:
    """Run the steps not done yet; returns PASSED, PAUSED or FAILED."""
    run = c.run
    names = run.state.setdefault("order", [s.name for s in steps])
    by_name = {s.name: s for s in steps}
    run.state["status"] = "running"
    run.save()
    for name in names:
        step = by_name[name]
        status = run.steps.get(name, {}).get("status")
        if status == "done":
            continue
        if status == "paused" and resuming and (step.manual or (step.done_when and step.done_when(c))):
            # The person did what the pause asked.
            run.mark(name, "done", by="person")
            c.log(f"{name}: done by hand")
            continue
        if step.manual and step.done_when and _holds(c, step):
            # Already as the step would leave it: nothing for anyone to do.
            run.mark(name, "done", by="already")
            c.log(f"{name}: already done")
            continue
        if step.manual:
            instructions, since = step.manual, c.now_ms()
            if step.auto and c.kit.taps_iphone:
                stopped = _tap(c, step, wait_for_code)
                if stopped is None:
                    run.mark(name, "done", by="harness")
                    c.save()
                    continue
                instructions = f"{step.manual}\n(The harness's own taps stopped: {stopped}. The screenshot shows where.)"
            # A code the taps already asked WhatsApp for still counts.
            return _pause(c, step, instructions, wait_for_code, since)
        c.log(f"{name}: start")
        try:
            step.run(c)
        except NeedsPerson as e:
            return _pause(c, step, str(e), wait_for_code)
        except Exception as e:  # noqa: BLE001 - every failure stops the run, reported with screenshots
            run.mark(name, "failed", error=str(e))
            shots = _screenshots(c, name)
            run.finish("failed", f"failed at {name}: {e}")
            c.save()
            notify(c.kit, "whatferry harness: failed", f"Failed at {name}: {e}\nRun folder: {run.folder}\n"
                   "Fix it, then: harness resume", urgent=True, attach=shots[0] if shots else None)
            return FAILED
        run.mark(name, "done")
        c.save()
    verdicts = [v for k, v in run.ctx.items() if k.endswith(".verdict")]
    summary = "passed: " + "; ".join(f"{k.split('.')[0]} {v['summary']}" for k, v in run.ctx.items()
                                     if k.endswith(".verdict"))
    run.finish("passed", summary if verdicts else "passed")
    c.save()
    notify(c.kit, "whatferry harness: passed", f"{run.state['summary']}\nRun folder: {run.folder}")
    return PASSED


def _screenshots(c: Context, label: str) -> list[Path]:
    shots = []
    for device, name in ((c._android, "pixel"), (c._iphone, "iphone")):
        if device is None:
            continue
        try:
            shot = device.screenshot(c.run.screenshot_path(f"{label}-{name}"))
        except Exception:  # noqa: BLE001 - a screenshot never hides the reason for stopping
            shot = None
        if shot:
            shots.append(shot)
    return shots


def _holds(c: Context, step: Step) -> bool:
    try:
        return bool(step.done_when(c))
    except Exception:  # noqa: BLE001 - can't tell: the step runs
        return False


def open_screen(c: Context):
    """A WDA session on the kit's iPhone (ios_ui.session); tests stand in for it."""
    automation = c.kit.ios_automation
    return ios_ui.session(c.kit.iphone_udid, automation.wda_app, automation.runner, c.log)


def _tap(c: Context, step: Step, wait_for_code) -> str | None:
    """Stage 2: the step's taps on the iPhone. None when done; otherwise why they stopped, for the pause."""
    c.log(f"{step.name}: the harness taps the iPhone")

    async def taps() -> str | None:
        try:
            async with open_screen(c) as screen:
                try:
                    await step.auto(screen, c, wait_for_code)
                except Exception as e:  # noqa: BLE001 - every stop falls back to the person
                    try:
                        c.run.screenshot_path(f"{step.name}-iphone-stopped").write_bytes(await screen.screenshot())
                    except Exception:  # noqa: BLE001
                        pass
                    return str(e) or type(e).__name__
        except Exception as e:  # noqa: BLE001 - WDA couldn't start: a person instead
            return str(e) or type(e).__name__
        return None

    stopped = asyncio.run(taps())
    if stopped:
        c.log(f"{step.name}: taps stopped: {stopped}")
    else:
        c.log(f"{step.name}: done by the harness")
    return stopped


def _pause(c: Context, step: Step, instructions: str, wait_for_code, since: int | None = None) -> int:
    run = c.run
    since = since or c.now_ms()
    run.mark(step.name, "paused", instructions=instructions)
    run.state.update(status="paused", paused_at=step.name)
    run.save()
    c.save()
    shot = None
    try:
        shot = c.iphone.screenshot(c.run.screenshot_path(f"{step.name}-iphone"))
    except Exception:  # noqa: BLE001
        pass
    notify(c.kit, "whatferry harness: your turn", f"{instructions}\nThen: harness resume\nRun folder: {run.folder}",
           urgent=True, attach=shot)
    c.log(f"{step.name}: paused for a person")
    if step.otp:
        code = wait_for_code(c.android, since)
        if code:
            notify(c.kit, "whatferry harness: code for B", f"WhatsApp's code for B: {code[:3]} {code[3:]}",
                   urgent=True)
            c.log(f"{step.name}: code sent on")
        else:
            c.log(f"{step.name}: no code arrived on the Pixel")
    return PAUSED
