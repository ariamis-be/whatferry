"""The private directory that holds decrypted databases and reports.

Everything decrypted lands here and nowhere else: one folder per run, outside
the repository by default. On macOS and Linux the folders are 0700 and the
files 0600. Windows ignores those modes; there the protection is the user
profile's own access list, which by default admits only that user (and
administrators), so the default location under the profile stays private.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

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


def write_private(path: Path, data: bytes) -> None:
    """Write a file only the owner can read, refusing to replace one."""
    fd = os.open(path, _WRITE_FLAGS, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


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
