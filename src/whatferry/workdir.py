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
import shutil
import stat
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


def home(platform: str = sys.platform, env=os.environ) -> Path:
    override = env.get("WHATFERRY_HOME")
    return Path(override).expanduser() if override else default_home(platform, env)


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


# A folder new_run made: 20261025-192744-backup, or -backup-2 for a second one that second.
_RUN = re.compile(r"^\d{8}-\d{6}-[a-z][a-z-]*?(-\d+)?$")
# Beside the run folders: Manifest.db copies the wizard compares, library temp
# files, and the wizard's progress, which only points at run folders.
_LEFTOVERS = ("snapshots", "tmp", "state.json")


def leftovers(root: Path, backups: bool = False) -> list[Path]:
    """What `whatferry clean` deletes from whatferry's folder, oldest run first.

    settings.json (the page's language and theme) and anything whatferry
    didn't name stay. The iPhone backups `whatferry ios backup` made stay
    unless asked for: they are the phone's, not a step's output.
    """
    if not root.is_dir():
        return []
    found = sorted(p for p in root.iterdir() if _RUN.match(p.name) and p.is_dir() and not p.is_symlink())
    names = _LEFTOVERS + (("backups",) if backups else ())
    return found + [root / name for name in names if (root / name).exists() or (root / name).is_symlink()]


def freed(paths: list[Path]) -> list[int]:
    """Bytes deleting each path gives back, without following links.

    A conversion hard-links its media, often to the Android media copy
    outside whatferry's folder: such a file counts once, toward the path
    holding its last link, and only when every link to it is among the paths.
    """
    sizes = [0] * len(paths)
    linked: dict[tuple[int, int], list] = {}  # (device, inode) -> [links seen, links, size, index of the last]
    for i, path in enumerate(paths):
        if path.is_symlink() or not path.is_dir():
            stats = [path.lstat()]
        else:
            stats = [os.lstat(os.path.join(folder, name)) for folder, dirs, files in os.walk(path)
                     for name in dirs + files]
        for st in stats:
            if st.st_nlink > 1 and stat.S_ISREG(st.st_mode):
                seen = linked.setdefault((st.st_dev, st.st_ino), [0, st.st_nlink, st.st_size, i])
                seen[0] += 1
                seen[3] = i
            else:
                sizes[i] += st.st_size
    for links_seen, links, size, i in linked.values():
        if links_seen >= links:
            sizes[i] += size
    return sizes


def remove(path: Path) -> None:
    """Delete a file or a whole folder; a link is removed, never followed."""
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)


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
