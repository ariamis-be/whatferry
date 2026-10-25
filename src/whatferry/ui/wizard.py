"""What the wizard does, without the web: steps, saved progress, background jobs.

Progress is saved to state.json in whatferry's private folder, so the wizard
can be closed while a backup is made and picked up again. It holds what the
reports hold (counts, paths, schema shape) and never a key or passphrase.
"""

import copy
import json
import re
import secrets
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from whatferry import adb, android, ios, ios_backup, sqlite_summary, workdir
from whatferry.ios_backup import Backup, BackupError

STEPS = ("start", "android", "before", "account", "after", "done")
CHECKLIST = ("add-account", "register-number", "leave-empty", "new-backup")

# Where people usually put the Android file once it reaches the computer.
CANDIDATE_FOLDERS = ("Downloads", "Desktop", "Documents", "whatferry-android", ".")
# Copies from the phone are named after the app and account, such as
# whatsapp-account-1001-msgstore.db.crypt15.
CANDIDATE_PATTERNS = ("*msgstore*.db.crypt15", "*msgstore*.db.crypt14", "*msgstore*.db")

MAX_LISTED_PATHS = 300


class StepError(Exception):
    """A step was asked for out of order, or with something missing."""


# Errors whose message is meant for the person using the wizard.
USER_ERRORS = (android.DecryptError, BackupError, StepError, adb.AdbError, OSError)

# Six or more digits in a row: a phone number or account ID inside a path.
_LONG_NUMBER = re.compile(r"\d{6,}")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class State:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        try:
            self._data = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def get(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    def update(self, **values) -> None:
        with self._lock:
            for key, value in values.items():
                if value is None:
                    self._data.pop(key, None)
                else:
                    self._data[key] = value
            self.path.parent.mkdir(parents=True, exist_ok=True)
            workdir.replace_private(self.path, json.dumps(self._data, indent=2, default=str).encode())


class Jobs:
    """Work that takes seconds to minutes, run off the request thread."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, fn) -> str:
        job_id = secrets.token_hex(8)
        job = {"status": "running"}
        with self._lock:
            self._jobs[job_id] = job

        def run():
            try:
                result = fn()
                update = {"status": "done", "result": result}
            except USER_ERRORS as e:
                update = {"status": "error", "error": str(e)}
            except Exception as e:  # noqa: BLE001 - shown to the person, logged in full
                traceback.print_exc(file=sys.stderr)
                update = {"status": "error", "error": f"unexpected error: {e!r}"}
            with self._lock:
                job.update(update)

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None


class Wizard:
    def __init__(self, home: Path | None = None):
        self.home = home or workdir.home()
        self.state = State(self.home / "state.json")
        self.jobs = Jobs()

    def overview(self) -> dict:
        return {
            "platform": sys.platform,
            "how_to_back_up": ios_backup.how_to_back_up(),
            "backup_roots": [str(r) for r in ios_backup.backup_roots()],
            "home": str(self.home),
            "candidate_folders": [str(Path.home() / f) if f != "." else str(Path.home())
                                  for f in CANDIDATE_FOLDERS],
            "phone_folder": str(adb.default_destination()),
            "state": (state := self.state.get()),
            "destination_hint": destination_hint(state),
        }

    def set_destination(self, choice: str) -> None:
        if choice not in DESTINATIONS:
            raise StepError(f"unknown destination {choice!r}")
        self.state.update(destination=choice)

    # Phone over USB

    def phone(self) -> dict:
        return adb.status()

    def phone_pull(self, serial: str, path: str) -> dict:
        tool = adb.find_adb()
        if tool is None:
            raise StepError("adb isn't installed")
        target = adb.pull(tool, serial, path)
        st = target.stat()
        return {"path": str(target), "name": target.name, "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")}

    # Android

    def android_candidates(self) -> list[dict]:
        seen, found = set(), []
        for folder in CANDIDATE_FOLDERS:
            base = Path.home() / folder
            for pattern in CANDIDATE_PATTERNS:
                try:
                    paths = sorted(base.glob(pattern))
                except OSError:
                    continue
                for p in paths:
                    if p.is_file() and p.resolve() not in seen:
                        seen.add(p.resolve())
                        st = p.stat()
                        found.append({"path": str(p), "name": p.name, "size": st.st_size,
                                      "modified": datetime.fromtimestamp(st.st_mtime).astimezone()
                                      .isoformat(timespec="seconds")})
        return sorted(found, key=lambda f: f["modified"], reverse=True)

    def android_upload_target(self, filename: str) -> Path:
        name = workdir.safe_relative(filename or "msgstore.db.crypt15").name
        return workdir.new_run("upload") / name

    def android_inspect(self, path: str, key_text: str | None) -> dict:
        source = Path(path).expanduser()
        with source.open("rb") as f:
            encrypted = not sqlite_summary.is_sqlite(f.read(16))
        if encrypted and not (key_text or "").strip():
            raise StepError("this backup is encrypted: enter its 64-digit key")
        key = android.parse_key(key_text) if encrypted else None
        report, run = android.inspect(source, key)
        entry = {"source": str(source), "run": str(run), "checked_at": _now(), "report": report.as_dict()}
        self.state.update(android=entry)
        return entry

    # iPhone

    def ios_backups(self) -> dict:
        try:
            listed = ios_backup.list_backups()
            error = None
        except BackupError as e:
            listed, error = [], str(e)
        return {
            "backups": [{"folder": str(folder), "id": folder.name, **vars(info)} for folder, info in listed],
            "error": error,
        }

    def ios_inspect(self, folder: str, passphrase: str | None, role: str) -> dict:
        if role not in ("before", "after"):
            raise StepError(f"unknown step {role!r}")
        before = self.state.get().get("before")
        if role == "after" and not before:
            raise StepError("check the first iPhone backup before the second")
        path = ios_backup.find_backup(folder)
        backup = Backup(path, passphrase or None)
        report, run = ios.inspect(backup)
        entry = {"folder": str(path), "run": str(run), "checked_at": _now(), "report": report.as_dict()}
        if role == "before":
            snapshot = ios_backup.snapshot_manifest(path, self.home / "snapshots" / run.name)
            entry["snapshot"] = str(snapshot)
            self.state.update(before=entry, after=None)
        else:
            old = Backup(Path(before["snapshot"]), passphrase or None)
            entry["diff"] = diff_summary(ios.diff(old, backup))
            self.state.update(after=entry)
        return entry

    # Progress

    def set_checklist(self, item: str, done: bool) -> dict:
        if item not in CHECKLIST:
            raise StepError(f"unknown checklist item {item!r}")
        checklist = self.state.get().get("checklist", {})
        checklist[item] = bool(done)
        self.state.update(checklist=checklist)
        return checklist

    def set_step(self, step: str) -> None:
        if step not in STEPS:
            raise StepError(f"unknown step {step!r}")
        self.state.update(step=step)

    def reset(self) -> None:
        """Forget progress; run folders and snapshots stay until deleted."""
        self.state.update(android=None, before=None, after=None, checklist=None, step=None, destination=None)

    def summary(self) -> str:
        return summary_text(self.state.get())


# Where the Android chats go on the iPhone:
#   setup     WhatsApp isn't set up there yet: set it up with the Android number
#   second    add the Android number as a second account (the usual case)
#   existing  an account already on the Android number takes them (a merge,
#             when it has chats of its own)
DESTINATIONS = ("setup", "second", "existing")


def destination_hint(state: dict) -> dict | None:
    """Which destination fits what the backups show, and why.

    Numbers are compared on their last two digits only (all the Android
    backup header keeps), so a match is likely, not certain.
    """
    before = state.get("before")
    if not before:
        return None
    report = before["report"]
    accounts = report.get("accounts", [])
    stores = [d for d in report["databases"] if Path(d["path"]).name == ios.CHAT_STORAGE]
    header = ((state.get("android") or {}).get("report") or {}).get("header") or {}
    ends = header.get("number_ends_with")
    # Checks saved before the current account detection (none, or the old
    # one that misread chats as accounts): say so, rather than compare.
    stale = report.get("accounts_method") != ios.ACCOUNTS_METHOD
    # A data/<id>/ folder is the only sign of a further account; its number
    # can't be read, so "full" only says there may already be two.
    folders = report.get("account_folders", [])
    # The main chat database's message count: what a merge into the main
    # account would merge with, whichever destination is picked by hand.
    main = next((d for d in stores if d["path"] == ios.CHAT_STORAGE), None)
    main_messages = (main or {}).get("counts", {}).get("messages")
    hint = {"android_ends": ends, "accounts": accounts, "full": len(accounts) + len(folders) >= 2, "stale": stale,
            "has_whatsapp": bool(stores or accounts), "main_messages": main_messages}
    if not stores and not accounts:
        return hint | {"suggested": "setup", "reason": "no-whatsapp"}
    # The iPhone gives the last four digits, the Android header only two.
    match = next((a for a in accounts if ends and (a.get("number_ends") or "").endswith(ends)), None)
    if match:
        messages = main_messages if match.get("main") else None
        return hint | {"suggested": "existing", "reason": "number-matches", "match": match, "messages": messages}
    if stale:
        return hint | {"suggested": "second", "reason": "stale-check"}
    if not ends:
        return hint | {"suggested": "second", "reason": "unknown-number"}
    known = [a for a in accounts if a.get("number_ends")]
    return hint | {"suggested": "second", "reason": "different-number" if known else "iphone-numbers-unknown"}


def diff_summary(d: ios.Diff) -> dict:
    def paths(entries):
        return [f"{e.domain}/{e.path}" for e in entries[:MAX_LISTED_PATHS]]

    added_stores = [e for e in d.added if Path(e.path).name == ios.CHAT_STORAGE]
    return {
        "added": len(d.added),
        "removed": len(d.removed),
        "changed": len(d.changed),
        "by_folder": {folder: dict(counts) for folder, counts in d.by_folder().items()},
        "added_paths": paths(d.added),
        "removed_paths": paths(d.removed),
        "changed_paths": paths([after for _, after in d.changed]),
        "new_chat_storages": [f"{e.domain}/{e.path}" for e in added_stores],
    }


def summary_text(state: dict) -> str:
    """The results as plain text to send on: shape and counts, nothing anyone wrote."""
    lines = ["whatferry discovery summary", ""]
    a = state.get("android")
    if a:
        r = a["report"]
        h = r.get("header") or {}
        lines += ["Android",
                  f"  WhatsApp {h.get('app_version') or '?'}, database version {r['user_version']}, "
                  f"{r['tables']} tables, {r['layout']}",
                  f"  messages {r.get('first_message') or '?'} to {r.get('last_message') or '?'}"]
        lines += [f"  {k}: {v}" for k, v in r["counts"].items() if v is not None]
        lines += [f"  jid server {k}: {v}" for k, v in r.get("jid_servers", {}).items()]
        lines += [f"  message types: {len(r.get('message_types', {}))}", ""]
    for role, title in (("before", "iPhone, first backup"), ("after", "iPhone, second backup")):
        entry = state.get(role)
        if not entry:
            continue
        r = entry["report"]
        d = r["device"]
        lines += [title,
                  f"  {d.get('model') or '?'}, iOS {d.get('ios_version') or '?'}, "
                  f"{'encrypted' if d.get('encrypted') else 'NOT encrypted'}, backup {d.get('backup_date') or '?'}"]
        lines += [f"  {dom}: {n['files']} files" for dom, n in r["domains"].items()]
        for db in r["databases"]:
            lines.append(f"  db {db['domain']}/{db['path']}: version {db['user_version']}, {db['tables']} tables")
            lines += [f"    {k}: {v}" for k, v in db.get("counts", {}).items() if v is not None]
            if db.get("core_data_entities"):
                lines.append(f"    entities: {len(db['core_data_entities'])}")
        for account in r.get("accounts", []):
            lines.append(f"  account id …{account['id_ends']}: number …{account.get('number_ends') or '?'}"
                         f"{' (' + account['country'] + ')' if account.get('country') else ''}"
                         f"{', main chat database' if account.get('main') else ''}")
        for folder in r.get("account_folders", []):
            lines.append(f"  account folder {folder['folder'][:13]}…: "
                         f"{'has' if folder['has_chat_database'] else 'no'} chat database")
        diff = entry.get("diff")
        if diff:
            lines.append(f"  diff: {diff['added']} added, {diff['removed']} removed, {diff['changed']} changed")
            lines += [f"    {folder}: " + ", ".join(f"{n} {k}" for k, n in counts.items())
                      for folder, counts in diff["by_folder"].items()]
            lines += [f"    new chat database: {p}" for p in diff["new_chat_storages"]]
        lines.append("")
    if state.get("destination"):
        hint = destination_hint(state) or {}
        lines += [f"Destination: {state['destination']} (suggested: {hint.get('suggested') or '?'}, "
                  f"{hint.get('reason') or 'no reason'})", ""]
    if len(lines) == 2:
        lines.append("Nothing checked yet.")
    # WhatsApp names folders after phone numbers; the shape survives without them.
    return _LONG_NUMBER.sub("<number>", "\n".join(lines).rstrip() + "\n")
