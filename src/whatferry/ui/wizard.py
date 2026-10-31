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

from whatferry import adb, android, backup_writer, convert, ios, ios_backup, preview, restore, sqlite_summary, workdir
from whatferry.backup_writer import WriteError
from whatferry.ios_backup import Backup, BackupError
from whatferry.restore import RestoreError

STEPS = ("start", "android", "before", "account", "after", "convert", "write", "restore", "done")
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
USER_ERRORS = (android.DecryptError, BackupError, StepError, adb.AdbError, convert.ConvertError, WriteError,
               RestoreError, preview.PreviewError, OSError)

# Android media folders: the copies made from the phone, one per account.
MEDIA_FOLDERS = ("whatferry-android", "whatferry-android/media")

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

    def start(self, fn, *, progress: bool = False) -> str:
        """Run fn in the background; with progress, fn gets a function to report a percentage through."""
        job_id = secrets.token_hex(8)
        job = {"status": "running"}
        with self._lock:
            self._jobs[job_id] = job

        def report(percent: float) -> None:
            with self._lock:
                job["progress"] = round(float(percent), 1)

        def run():
            try:
                result = fn(report) if progress else fn()
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
        # The page's language and theme. Kept here, not in the browser: the
        # wizard gets a new port each start, and a browser keeps its storage
        # per port. A reset leaves them alone.
        self.settings = State(self.home / "settings.json")
        self.jobs = Jobs()

    SETTINGS = {"lang": ("en", "zh"), "theme": ("light", "dark", "system")}

    def set_settings(self, values: dict) -> dict:
        for key, value in values.items():
            if key not in self.SETTINGS or value not in self.SETTINGS[key]:
                raise StepError(f"unknown setting {key}={value}")
        self.settings.update(**values)
        return self.settings.get()

    # Several Android accounts, moved one after another. The current account's
    # android/destination/after sit at the top of the state, where every step
    # reads them; each account's own copy is kept in "accounts" by key (its
    # backup file's path), and "current" names the one on top.
    PER_ACCOUNT = ("android", "destination", "after", "converted", "written", "restored")
    # Made from the checked backups: dropped whenever one is checked again,
    # so no step shows as done from something older.
    LATER = ("converted", "written", "restored")

    def _stash(self) -> dict:
        """Every account's data, the current one's refreshed from the top."""
        state = self.state.get()
        accounts = state.get("accounts") or {}
        key = state.get("current")
        if not key and state.get("android"):
            # Saved before accounts were kept apart: adopt it as the first.
            key = str(Path(state["android"]["source"]).expanduser().resolve())
            self.state.update(current=key)
        if key:
            accounts[key] = {k: state.get(k) for k in self.PER_ACCOUNT}
        return accounts

    def _switch(self, key: str, accounts: dict) -> None:
        saved = accounts.get(key, {})
        self.state.update(accounts=accounts, current=key, **{k: saved.get(k) for k in self.PER_ACCOUNT})

    def select_android(self, key: str) -> None:
        accounts = self._stash()
        if key not in accounts:
            raise StepError("no such Android account: check its backup first")
        self._switch(key, accounts)

    def overview(self) -> dict:
        if self.state.get().get("android") and not self.state.get().get("current"):
            self.state.update(accounts=self._stash())
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
            "android_accounts": android_accounts(state),
        }

    def set_destination(self, choice: str) -> None:
        if choice not in DESTINATIONS:
            raise StepError(f"unknown destination {choice!r}")
        self.state.update(destination=choice)
        self.state.update(accounts=self._stash())

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
        # Another backup file is another Android account: the current one is
        # put aside, and checking the same file again keeps its progress.
        accounts = self._stash()
        key = str(source.resolve())
        accounts.setdefault(key, {}).update(android=entry, **dict.fromkeys(self.LATER))
        self._switch(key, accounts)
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
            # Every account's second backup and transfer came from the old first backup.
            accounts = self._stash()
            for account in accounts.values():
                account.update(after=None, **dict.fromkeys(self.LATER))
            self.state.update(before=entry, after=None, accounts=accounts or None, **dict.fromkeys(self.LATER))
        else:
            old = Backup(Path(before["snapshot"]), passphrase or None)
            entry["diff"] = diff_summary(ios.diff(old, backup))
            self.state.update(after=entry, **dict.fromkeys(self.LATER))
            self.state.update(accounts=self._stash())
        return entry

    # Convert, write, restore: the current Android account's chats into the
    # iPhone account picked, then into a copy of the backup they came from,
    # then onto the phone. Each step's record is dropped when an earlier one
    # is redone, so a later step never works from something stale.

    def _account_update(self, **values) -> None:
        self.state.update(**values)
        self.state.update(accounts=self._stash())

    def convert_options(self) -> dict:
        state = self.state.get()
        android_entry, iphone = state.get("android"), iphone_entry(state)
        if not android_entry or not iphone:
            raise StepError("check the Android backup and the iPhone backup first")
        media = media_candidates(Path(android_entry["run"]) / "msgstore.db")
        return {
            "backup": iphone["folder"],
            "backup_checked_at": iphone["checked_at"],
            "second_backup": bool(state.get("after")),
            "targets": convert_targets(state),
            "media": media,
        }

    def make_conversion(self, account_folder: str | None, media: str | None) -> dict:
        state = self.state.get()
        android_entry, iphone = state.get("android"), iphone_entry(state)
        if not android_entry or not iphone:
            raise StepError("check the Android backup and the iPhone backup first")
        account_folder = account_folder or None
        if account_folder not in {t["folder"] for t in convert_targets(state)}:
            raise StepError("that iPhone account isn't in the checked backup")
        android_db = Path(android_entry["run"]) / "msgstore.db"
        ios_db = (Path(iphone["run"]) / "files" / workdir.safe_relative(ios.SHARED_DOMAIN)
                  / workdir.safe_relative(f"{account_folder + '/' if account_folder else ''}{ios.CHAT_STORAGE}"))
        if not android_db.is_file() or not ios_db.is_file():
            raise StepError("the checked copies are gone: check both backups again")
        media_root = Path(media).expanduser() if media else None
        if media_root and not media_root.is_dir():
            raise StepError(f"{media_root} isn't a folder")
        app = ((android_entry["report"].get("header") or {}).get("app_version"))
        report, run = convert.convert(android_db, ios_db, media_root, account_folder, android_app=app)
        entry = {"run": str(run), "backup": iphone["folder"], "account_folder": account_folder, "ios_db": str(ios_db),
                 "media": str(media_root) if media_root else None, "made_at": _now(), "report": report.as_dict()}
        self._account_update(converted=entry, written=None, restored=None)
        return entry

    # The preview: the merged database read back, names and message text
    # included. Answered to the page only, never saved.

    def _preview(self) -> preview.Preview:
        converted = self.state.get().get("converted")
        if not converted:
            raise StepError("convert first")
        if not converted.get("ios_db"):
            raise StepError("this conversion was made before previews existed: convert again")
        ios_db, run, folder = Path(converted["ios_db"]), Path(converted["run"]), converted["account_folder"]
        # The account's own contacts first, then the main account's.
        shared = ios_db.parents[2] if folder else ios_db.parent
        names = preview.contact_names(ios_db.parent / "ContactsV2.sqlite", shared / "ContactsV2.sqlite")
        return preview.Preview(run / "files" / ios.CHAT_STORAGE, ios_db, names,
                               run / "files" / workdir.safe_relative(folder or ".") / "Message")

    def preview_chats(self) -> dict:
        chats = self._preview().chats()
        return {"chats": chats, "totals": {
            change: sum(c["change"] == change for c in chats) for change in ("new", "joined", "unchanged")
        } | {"from_android": sum(c["from_android"] for c in chats)}}

    def preview_messages(self, chat: int, limit: int = 60) -> dict:
        return {"messages": self._preview().messages(chat, limit)}

    def preview_picture(self, message: int) -> dict:
        return {"data": self._preview().picture(message)}

    def write_backup(self, passphrase: str | None, skip_source_check: bool = False) -> dict:
        converted = self.state.get().get("converted")
        if not converted:
            raise StepError("convert first")
        report, target = backup_writer.write_conversion(Path(converted["backup"]), passphrase or None,
                                                        Path(converted["run"]), converted["account_folder"],
                                                        check_source=not skip_source_check)
        entry = {"folder": str(target), "from": converted["backup"], "made_at": _now(), "report": report.as_dict()}
        self._account_update(written=entry, restored=None)
        return entry

    def restore_status(self) -> dict:
        written = self.state.get().get("written")
        try:
            phones, error = [p.as_dict() for p in restore.iphones()], None
        except RestoreError as e:
            phones, error = [], str(e)
        return {"phones": phones, "error": error, "udid": Path(written["folder"]).name if written else None}

    def restore_backup(self, passphrase: str | None, confirmed: bool, progress=lambda _: None) -> dict:
        written = self.state.get().get("written")
        if not written:
            raise StepError("write the new backup first")
        if not confirmed:
            raise StepError("confirm the restore first")
        folder = Path(written["folder"])
        if ios_backup.device_info(folder).encrypted:
            Backup(folder, passphrase or None)  # a wrong passphrase stops here, before the phone is touched
        phone = restore.restore(folder, passphrase or None, progress)
        entry = {"folder": str(folder), "phone": phone.name, "restored_at": _now()}
        self._account_update(restored=entry)
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
        self.state.update(before=None, checklist=None, step=None, accounts=None, current=None,
                          **dict.fromkeys(self.PER_ACCOUNT))

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
    # Folders already tied to a known account don't count twice.
    linked = {a.get("folder") for a in accounts}
    folders = [f for f in report.get("account_folders", []) if f["folder"] not in linked]
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
    if match and not match.get("main") and not match.get("has_chats"):
        # The Android number was added as a second account, but WhatsApp has
        # no chats for it yet: usually because signing in stopped before the
        # confirmation code. Finishing it creates the database, and the
        # second backup is what finds it, so this is the second-account path.
        return hint | {"suggested": "second", "reason": "second-started", "match": match}
    if match:
        messages = main_messages if match.get("main") else None
        return hint | {"suggested": "existing", "reason": "number-matches", "match": match, "messages": messages}
    if stale:
        return hint | {"suggested": "second", "reason": "stale-check"}
    if not ends:
        return hint | {"suggested": "second", "reason": "unknown-number"}
    known = [a for a in accounts if a.get("number_ends")]
    return hint | {"suggested": "second", "reason": "different-number" if known else "iphone-numbers-unknown"}


def iphone_entry(state: dict) -> dict | None:
    """The iPhone backup the chats go into: the second one when made, else the first."""
    return state.get("after") or state.get("before")


def convert_targets(state: dict) -> list[dict]:
    """The checked backup's WhatsApp accounts with chat databases, the likely one marked."""
    iphone = iphone_entry(state)
    if not iphone:
        return []
    report = iphone["report"]
    accounts = report.get("accounts", [])
    targets = []
    for db in report["databases"]:
        if db["domain"] != ios.SHARED_DOMAIN or Path(db["path"]).name != ios.CHAT_STORAGE:
            continue
        folder = db["path"].rpartition("/")[0] or None
        account = next((a for a in accounts if (a.get("folder") == folder if folder else a.get("main"))), None) or {}
        targets.append({"folder": folder, "main": folder is None, "number_ends": account.get("number_ends"),
                        "country": account.get("country"), "messages": (db.get("counts") or {}).get("messages"),
                        "suggested": False})
    # The likely one: the account the destination check matched, else the
    # one on the Android number, else a chat database the second backup added.
    hint = destination_hint(state) or {}
    match = hint.get("match")
    ends = hint.get("android_ends")
    added = {p.removeprefix(f"{ios.SHARED_DOMAIN}/").rpartition("/")[0] or None
             for p in (iphone.get("diff") or {}).get("new_chat_storages", [])}
    pick = (next((t for t in targets if match and t["folder"] == (None if match.get("main") else match.get("folder"))),
                 None)
            or next((t for t in targets if ends and (t["number_ends"] or "").endswith(ends)), None)
            or next((t for t in targets if t["folder"] in added), None)
            or (targets[0] if len(targets) == 1 else None))
    if pick:
        pick["suggested"] = True
    return targets


def media_candidates(android_db: Path) -> list[dict]:
    """Folders holding a copy of an Android WhatsApp Media folder; the one that has this history's files marked.

    One per account looks the same from outside, so each is asked how many
    of the newest media files the Android history names it has.
    """
    seen, found = set(), []
    for base in MEDIA_FOLDERS:
        root = Path.home() / base
        try:
            folders = [root, *sorted(p for p in root.iterdir() if p.is_dir())] if root.is_dir() else []
        except OSError:
            continue
        for folder in folders:
            if folder.resolve() in seen or not any(folder.glob("WhatsApp *")):
                continue
            seen.add(folder.resolve())
            has, of = convert.media_found(android_db, folder)
            found.append({"path": str(folder), "name": folder.name, "found": has, "sampled": of, "suggested": False})
    best = max(found, key=lambda m: m["found"], default=None)
    if best and best["found"]:
        best["suggested"] = True
    return found


def android_accounts(state: dict) -> list[dict]:
    """The Android accounts checked so far, for the page to switch between."""
    out = []
    for key, account in (state.get("accounts") or {}).items():
        report = ((account.get("android") or {}).get("report")) or {}
        out.append({
            "key": key,
            "name": Path(key).name,
            "number_ends": (report.get("header") or {}).get("number_ends_with"),
            "messages": (report.get("counts") or {}).get("messages"),
            "destination": account.get("destination"),
            "second_backup_checked": bool(account.get("after")),
            "current": key == state.get("current"),
        })
    return out


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
    """The results as plain text to send on: shape and counts, nothing anyone wrote.

    The iPhone's first backup once, then each Android account with where it
    goes and, when made, the second iPhone backup that goes with it.
    """
    lines = ["whatferry discovery summary", ""]
    if state.get("before"):
        lines += _iphone_lines("iPhone, first backup", state["before"])
    # Without accounts kept apart (one account, or none checked yet), what's
    # on top is the only one.
    on_top = {k: state.get(k) for k in Wizard.PER_ACCOUNT}
    accounts = state.get("accounts") or ({state.get("current"): on_top} if any(on_top.values()) else {})
    for key, account in accounts.items():
        if key == state.get("current"):
            account = {k: state.get(k) for k in Wizard.PER_ACCOUNT}
        android = account.get("android")
        if android:
            lines += _android_lines(android["report"])
        if account.get("destination"):
            hint = destination_hint(state | account) or {}
            lines += [f"  Destination: {account['destination']} (suggested: {hint.get('suggested') or '?'}, "
                      f"{hint.get('reason') or 'no reason'})"]
        if account.get("after"):
            lines += [""] + _iphone_lines("  iPhone, second backup for this account", account["after"])
        lines.append("")
    if len(lines) == 2:
        lines.append("Nothing checked yet.")
    # WhatsApp names folders after phone numbers; the shape survives without them.
    return _LONG_NUMBER.sub("<number>", "\n".join(lines).rstrip() + "\n")


def _android_lines(r: dict) -> list[str]:
    h = r.get("header") or {}
    lines = [f"Android account, number ending {h.get('number_ends_with') or '?'}",
             f"  WhatsApp {h.get('app_version') or '?'}, database version {r['user_version']}, "
             f"{r['tables']} tables, {r['layout']}",
             f"  messages {r.get('first_message') or '?'} to {r.get('last_message') or '?'}"]
    lines += [f"  {k}: {v}" for k, v in r["counts"].items() if v is not None]
    lines += [f"  jid server {k}: {v}" for k, v in r.get("jid_servers", {}).items()]
    lines.append(f"  message types: {len(r.get('message_types', {}))}")
    return lines


def _iphone_lines(title: str, entry: dict) -> list[str]:
    r = entry["report"]
    d = r["device"]
    lines = [title,
             f"  {d.get('model') or '?'}, iOS {d.get('ios_version') or '?'}, "
             f"{'encrypted' if d.get('encrypted') else 'NOT encrypted'}, backup {d.get('backup_date') or '?'}"]
    lines += [f"  {dom}: {n['files']} files" for dom, n in r["domains"].items()]
    for db in r["databases"]:
        lines.append(f"  db {db['domain']}/{db['path']}: version {db['user_version']}, {db['tables']} tables")
        lines += [f"    {k}: {v}" for k, v in db.get("counts", {}).items() if v is not None]
        if db.get("core_data_entities"):
            lines.append(f"    entities: {len(db['core_data_entities'])}")
    for account in r.get("accounts", []):
        lines.append(f"  account id …{account.get('id_ends') or '?'}: number …{account.get('number_ends') or '?'}"
                     f"{' (' + account['country'] + ')' if account.get('country') else ''}"
                     f"{', main chat database' if account.get('main') else ', second account'}"
                     f"{'' if account.get('has_chats', account.get('main')) else ', no chats in backup'}")
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
    return lines
