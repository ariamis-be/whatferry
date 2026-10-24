"""The private directory that holds decrypted databases and reports.

Everything decrypted lands here and nowhere else: one folder per run, readable
only by the owner, outside the repository by default.
"""

import os
from datetime import datetime
from pathlib import Path

DEFAULT_HOME = Path.home() / ".local" / "share" / "whatferry"


def home() -> Path:
    return Path(os.environ.get("WHATFERRY_HOME", DEFAULT_HOME)).expanduser()


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
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
