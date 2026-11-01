"""Copy WhatsApp backups off, and a written one onto, an Android phone with adb (USB debugging).

Lists WhatsApp's backup files and pulls one; a pull is only allowed for a
path the same phone listed a moment before, so nothing here can be used to
read other files off the phone. The one write, `push`, only goes into one of
WhatsApp's own folders and never replaces a file already there.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Where people get adb: Android Studio's SDK, the standalone platform-tools,
# package managers (on PATH), or mise's android-sdk.
SDK_FOLDERS = (
    "~/Library/Android/sdk",
    "~/Android/Sdk",
    "~/AppData/Local/Android/Sdk",
)
MISE_SDKS = "~/.local/share/mise/installs/android-sdk"

# Every place WhatsApp and WhatsApp Business keep backups: per account on
# phones with more than one account (accounts/<n>/), the shared folder on
# phones with one, and the pre-Android 11 location.
BACKUP_GLOBS = (
    "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/msgstore*",
    "/sdcard/Android/media/com.whatsapp/WhatsApp/accounts/*/Databases/msgstore*",
    "'/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business'/Databases/msgstore*",
    "'/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business'/accounts/*/Databases/msgstore*",
    "/sdcard/WhatsApp/Databases/msgstore*",
    "'/sdcard/WhatsApp Business'/Databases/msgstore*",
)

TIMEOUT = 30
PULL_TIMEOUT = 600
# Copies over USB, and moves on the phone's storage, get this much longer
# per byte on top of PULL_TIMEOUT: a slow cable does about 5 MB/s.
SLOW_BYTES_PER_SECOND = 5_000_000


def _timeout_for(size: int) -> int:
    return PULL_TIMEOUT + size // SLOW_BYTES_PER_SECOND

# A phone says what it can do in `adb devices`: only "device" can be used.
STATES = {
    "device": "ready",
    "unauthorized": "Unlock the phone and tap Allow on “Allow USB debugging?”.",
    "offline": "The phone isn't answering: unplug it, plug it back in, and unlock it.",
    "no permissions": "This computer isn't allowed to talk to the phone (on Linux, add a udev rule for Android).",
    "authorizing": "Waiting for you to tap Allow on the phone.",
}


class AdbError(Exception):
    pass


def find_adb(env=os.environ) -> Path | None:
    """The first adb that runs: WHATFERRY_ADB, PATH, then the usual SDK folders.

    Each candidate must answer `adb version`: a version-manager shim on PATH
    can exist and still refuse to run outside its project.
    """
    exe = "adb.exe" if sys.platform == "win32" else "adb"
    if env.get("WHATFERRY_ADB"):
        return Path(env["WHATFERRY_ADB"]).expanduser()
    candidates = [Path(p) for p in [shutil.which("adb")] if p]
    candidates += [Path(env[v]) / "platform-tools" / exe
                   for v in ("ANDROID_HOME", "ANDROID_SDK_ROOT") if env.get(v)]
    candidates += [Path(p).expanduser() / "platform-tools" / exe for p in SDK_FOLDERS]
    if env.get("LOCALAPPDATA"):
        candidates.append(Path(env["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools" / exe)
    candidates += sorted(Path(MISE_SDKS).expanduser().glob(f"*/platform-tools/{exe}"), reverse=True)
    return next((c for c in candidates if c.is_file() and _answers(c)), None)


def _answers(adb: Path) -> bool:
    try:
        result = subprocess.run([str(adb), "version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "Android Debug Bridge" in result.stdout


def _run(adb: Path, *args: str, timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([str(adb), *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise AdbError(f"adb not found at {adb}") from None
    except subprocess.TimeoutExpired:
        raise AdbError("adb didn't answer in time: unplug the phone, plug it back in, and unlock it") from None


@dataclass
class Device:
    serial: str
    state: str
    model: str | None
    ready: bool
    advice: str | None


def devices(adb: Path) -> list[Device]:
    result = _run(adb, "devices", "-l")
    if result.returncode != 0:
        raise AdbError(f"adb couldn't list phones: {(result.stderr or result.stdout).strip() or 'no reason given'}")
    out = result.stdout
    found = []
    for line in out.splitlines()[1:]:
        if not line.strip() or line.startswith("*"):
            continue
        serial, _, rest = line.partition(" ")
        rest = rest.strip()
        state = next((s for s in STATES if rest.startswith(s)), rest.split(" ")[0] if rest else "unknown")
        model = re.search(r"\bmodel:(\S+)", rest)
        found.append(Device(
            serial=serial.strip(), state=state,
            model=model.group(1).replace("_", " ") if model else None,
            ready=state == "device",
            advice=None if state == "device" else STATES.get(state, f"adb says “{state}”."),
        ))
    return found


@dataclass
class PhoneBackup:
    path: str
    name: str
    size: int
    modified: str
    app: str
    account: str | None
    kind: str
    usable: bool
    note: str | None

    @property
    def local_name(self) -> str:
        app = "whatsapp-business" if self.app == "WhatsApp Business" else "whatsapp"
        account = f"-account-{self.account}" if self.account else ""
        return f"{app}{account}-{self.name}"


def _describe(path: str, size: int, mtime: int) -> PhoneBackup:
    name = path.rsplit("/", 1)[-1]
    account = re.search(r"/accounts/(\d+)/", path)
    if name.endswith(".crypt15"):
        kind, usable, note = "crypt15", True, None
    elif re.search(r"\.crypt1[24]$", name):
        kind, usable = name.rsplit(".", 1)[-1], False
        note = ("Older encryption: its key only exists on a rooted phone. Turn on the 64-digit "
                "encrypted backup and back up again to get a .crypt15 file.")
    elif name.endswith(".db"):
        kind, usable, note = "plain", True, None
    else:
        kind, usable, note = "other", False, "Not a WhatsApp chat backup."
    if "increment" in name:
        usable, note = False, "A partial (incremental) backup; use the full msgstore file."
    return PhoneBackup(
        path=path, name=name, size=size,
        modified=datetime.fromtimestamp(mtime).astimezone().isoformat(timespec="seconds"),
        app="WhatsApp Business" if "w4b" in path or "WhatsApp Business" in path else "WhatsApp",
        account=account.group(1) if account else None,
        kind=kind, usable=usable, note=note,
    )


def phone_backups(adb: Path, serial: str) -> list[PhoneBackup]:
    """Every WhatsApp chat backup on the phone, newest first."""
    # stat on globs the phone's own shell expands; folders that don't exist
    # just print nothing.
    # `; true`: stat fails for globs that match nothing, which is fine; a
    # failure of adb itself (the phone gone) still shows.
    command = "stat -c '%s|%Y|%n' " + " ".join(BACKUP_GLOBS) + " 2>/dev/null; true"
    result = _run(adb, "-s", serial, "shell", command)
    if result.returncode != 0:
        raise AdbError(f"the phone didn't answer: {(result.stderr or result.stdout).strip() or 'adb gave no reason'}")
    out = result.stdout
    found = []
    for line in out.splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            found.append(_describe(parts[2], int(parts[0]), int(parts[1])))
    # Usable first, then newest.
    return sorted(found, key=lambda b: (b.usable, b.modified), reverse=True)


def default_destination() -> Path:
    return Path.home() / "whatferry-android"


def pull(adb: Path, serial: str, remote: str, dest_folder: Path | None = None) -> Path:
    """Copy one backup the phone just listed into a private folder."""
    listed = {b.path: b for b in phone_backups(adb, serial)}
    backup = listed.get(remote)
    if backup is None:
        raise AdbError("that file isn't one of the phone's WhatsApp backups (list them again)")
    folder = dest_folder or default_destination()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / backup.local_name
    partial = folder / f".{backup.local_name}.part"
    partial.unlink(missing_ok=True)
    result = _run(adb, "-s", serial, "pull", remote, str(partial), timeout=_timeout_for(backup.size))
    if result.returncode != 0 or not partial.exists():
        partial.unlink(missing_ok=True)
        raise AdbError(f"copying failed: {(result.stderr or result.stdout).strip() or 'adb gave no reason'}")
    if (got := partial.stat().st_size) != backup.size:
        partial.unlink()
        raise AdbError(f"the copy is incomplete ({got} of {backup.size} bytes): let WhatsApp finish its backup, "
                       "then copy again")
    partial.chmod(0o600)
    os.replace(partial, target)
    return target


WHATSAPP_ROOT = "/sdcard/Android/media/com.whatsapp/WhatsApp"


def whatsapp_folders(adb: Path, serial: str) -> list[str]:
    """Where WhatsApp keeps an account's backup and media: the main folder, and accounts/<n>/ ones listed."""
    found = {WHATSAPP_ROOT}
    for backup in phone_backups(adb, serial):
        if backup.path.startswith(f"{WHATSAPP_ROOT}/accounts/") and "/Databases/" in backup.path:
            found.add(backup.path.split("/Databases/")[0])
    return sorted(found)


def push(adb: Path, serial: str, root: str, folder: Path) -> dict:
    """Copy a written WhatsApp/ folder onto the phone, into one of its WhatsApp folders.

    Nothing on the phone is replaced: a backup already there is kept under a
    new name (WhatsApp only restores msgstore.db.crypt15), and media files
    are copied without overwriting any file of the same name. If a step
    fails, what changed so far is undone where it can be, and the error says
    what is left.
    """
    if root not in whatsapp_folders(adb, serial):
        raise AdbError("that isn't one of the phone's WhatsApp folders (list them again)")
    backup = folder / "Databases" / "msgstore.db.crypt15"
    if not backup.is_file():
        raise AdbError(f"{folder} has no Databases/msgstore.db.crypt15")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    remote = f"{root}/Databases/msgstore.db.crypt15"
    kept = f"{remote}.before-whatferry-{stamp}"
    q = shlex.quote
    _shell(adb, serial, f"mkdir -p {q(root + '/Databases')} {q(root + '/Media')}")
    media = folder / "Media"
    files = [p for p in media.rglob("*") if p.is_file()] if media.is_dir() else []
    size = sum(p.stat().st_size for p in files)
    staging = f"{root}/.whatferry-{stamp}"
    phone_media = q(root + "/Media")
    if files:
        # Media first, into a staging folder: if the phone already has a file
        # under one of these names, stop before anything on it has changed.
        try:
            _push(adb, serial, media, staging, _timeout_for(size))
            clashes = _shell(adb, serial, f"cd {q(staging)} && find . -type f | while IFS= read -r f; do "
                                          f"[ -e {phone_media}/\"$f\" ] && echo \"$f\"; done; true").splitlines()
        except AdbError:
            _remove_quietly(adb, serial, staging)
            raise
        if clashes:
            _remove_quietly(adb, serial, staging)
            raise AdbError(f"the phone already has {len(clashes)} file(s) under names the conversion uses "
                           f"(such as {clashes[0].removeprefix('./')}); nothing was changed")
        # Then moved, not copied, into Media: the same storage, so each file
        # is only renamed, however large the folder is.
        try:
            _shell(adb, serial, f"cd {q(staging)} && find . -type f | while IFS= read -r f; do "
                                f"mkdir -p {phone_media}/\"$(dirname \"$f\")\" && "
                                f"mv -n \"$f\" {phone_media}/\"$f\" || exit 1; done", timeout=_timeout_for(size))
        except AdbError as e:
            _remove_quietly(adb, serial, staging)
            raise AdbError(f"{e} (some media files may already be in {root}/Media; "
                           "the phone's backup is unchanged)") from None
        _remove_quietly(adb, serial, staging)
    answer = _shell(adb, serial, f"if [ -e {q(remote)} ]; then mv {q(remote)} {q(kept)} && echo kept; fi")
    try:
        _push(adb, serial, backup, remote, _timeout_for(backup.stat().st_size))
    except AdbError as e:
        if "kept" not in answer:
            raise
        try:
            _shell(adb, serial, f"rm -f {q(remote)} && mv {q(kept)} {q(remote)}")
        except AdbError:
            raise AdbError(f"{e} (the phone's own backup is kept as {kept}: "
                           "rename it back to msgstore.db.crypt15)") from None
        raise AdbError(f"{e} (the phone's own backup is back in place)") from None
    return {"root": root, "kept": kept if "kept" in answer else None, "media_files": len(files)}


def _remove_quietly(adb: Path, serial: str, remote: str) -> None:
    try:
        _shell(adb, serial, f"rm -rf {shlex.quote(remote)}")
    except AdbError:
        pass


def _shell(adb: Path, serial: str, command: str, timeout: int = TIMEOUT) -> str:
    result = _run(adb, "-s", serial, "shell", command, timeout=timeout)
    if result.returncode != 0:
        raise AdbError(f"the phone refused: {(result.stderr or result.stdout).strip() or 'adb gave no reason'}")
    return result.stdout


def _push(adb: Path, serial: str, local: Path, remote: str, timeout: int = PULL_TIMEOUT) -> None:
    result = _run(adb, "-s", serial, "push", str(local), remote, timeout=timeout)
    if result.returncode != 0:
        raise AdbError(f"copying to the phone failed: {(result.stderr or result.stdout).strip() or 'adb gave no reason'}")


def status() -> dict:
    """What the wizard shows: is adb there, which phones, which backups on each."""
    adb = find_adb()
    if adb is None:
        return {"adb": None, "devices": []}
    try:
        phones = devices(adb)
    except AdbError as e:
        return {"adb": str(adb), "devices": [], "error": str(e)}
    out = []
    for phone in phones:
        entry = asdict(phone)
        if phone.ready:
            try:
                entry["backups"] = [asdict(b) | {"local_name": b.local_name} for b in phone_backups(adb, phone.serial)]
            except AdbError as e:
                entry["backups"], entry["error"] = [], str(e)
        out.append(entry)
    return {"adb": str(adb), "devices": out}
