"""The private directory that holds decrypted databases and reports.

Everything decrypted lands here and nowhere else: one folder per run, outside
the repository by default. On macOS and Linux the folders are 0700 and the
files 0600. Windows ignores those modes; there the protection is the user
profile's own access list, which by default admits only that user (and
administrators), so the default location under the profile stays private.
"""

import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

# Without O_BINARY, Windows opens the descriptor in text mode and rewrites
# every \n byte as \r\n, corrupting any database written through it.
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)

# Characters Windows refuses in a file name, plus ASCII control characters.
_UNSAFE = re.compile(r'[<>:"|?*\\\x00-\x1f]')
# Names Windows reserves whatever the extension: CON, NUL, COM1, LPT1, ...
_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.IGNORECASE)


def default_home(platform: str = sys.platform, env=os.environ) -> Path:
    """%LOCALAPPDATA%\\whatferry on Windows, $XDG_DATA_HOME/whatferry elsewhere."""
    if platform == "win32":
        base = env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    else:
        base = env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "whatferry"


def home() -> Path:
    override = os.environ.get("WHATFERRY_HOME")
    return Path(override).expanduser() if override else default_home()


def new_run(kind: str) -> Path:
    """Create a fresh, owner-only folder for one command's output."""
    root = home()
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run = root / f"{stamp}-{kind}"
    suffix = 1
    while run.exists():
        suffix += 1
        run = root / f"{stamp}-{kind}-{suffix}"
    run.mkdir(mode=0o700)
    return run


def private_temp() -> Path:
    """An owner-only folder for a library's temporary files, in place of the system's shared one."""
    folder = home() / "tmp"
    folder.mkdir(parents=True, exist_ok=True)
    home().chmod(0o700)
    folder.chmod(0o700)
    return folder


def open_private(path: Path) -> BinaryIO:
    """A new file only the owner can read, open for binary writing.

    Refuses to replace an existing file.
    """
    return os.fdopen(os.open(path, _WRITE_FLAGS, 0o600), "wb")


def write_private(path: Path, data: bytes) -> None:
    with open_private(path) as f:
        f.write(data)


def copy_private(source: Path, path: Path) -> str:
    """Copy a file into a new owner-only one, in chunks; returns the SHA-256 of what was copied."""
    digest = hashlib.sha256()
    with source.open("rb") as src, open_private(path) as out:
        while chunk := src.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest()


def replace_private(path: Path, data: bytes) -> None:
    """Replace a file's contents in one step, through an owner-only temporary file."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{datetime.now().timestamp():.6f}.tmp")
    write_private(tmp, data)
    os.replace(tmp, path)


def safe_relative(path: str) -> Path:
    """An iPhone relative path as one that is valid on macOS, Windows and Linux.

    The same rewrite applies everywhere, so a report names the same file on
    every platform. Empty, `.` and `..` parts are dropped, so the result can
    never climb out of the folder it is joined to.
    """
    parts = []
    for part in path.split("/"):
        if part in ("", ".", ".."):
            continue
        part = _UNSAFE.sub("_", part).rstrip(" .") or "_"
        if _RESERVED.match(part):
            part = "_" + part
        parts.append(part)
    return Path(*parts) if parts else Path("_")
