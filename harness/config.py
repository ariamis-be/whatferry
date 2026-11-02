"""The test kit: one secrets file, and the folder everything the harness makes goes in.

The secrets file is TOML, readable by its owner only (0600), and holds what
a run needs and nobody else should see: the iPhone backup passphrase, the
Android key, B's number, and the two phones allowed. Nothing in it is ever
logged or reported.

    backup_passphrase = "…"           # the test iPhone's backup passphrase
    number_b = "+32 470 00 00 00"     # the ferried number, as typed into WhatsApp
    iphone_udid = "00008160-…"        # the only iPhone the harness touches
    android_serial = "1A2B3C4D5E6F70" # the only Android phone it touches
    android_key = "…64 characters…"   # 0-9 and a-f; written by the harness when it reads one

    [notify]
    ntfy = "https://ntfy.sh/<a long random topic>"   # and/or:
    mail_to = "you@example.com"
    smtp_host = "smtp.example.com"
    smtp_user = "…"
    smtp_password = "…"
"""

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SECRETS = Path("~/.config/whatferry-harness/secrets.toml")
DEFAULT_HOME = Path("~/whatferry-harness")
REQUIRED = ("backup_passphrase", "number_b", "iphone_udid", "android_serial")
_KEY = re.compile(r"^[0-9a-f]{64}$")


class KitError(Exception):
    """The kit is not as the harness needs it; the message says what to fix."""


@dataclass
class Notify:
    ntfy: str | None = None
    mail_to: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None


@dataclass
class Kit:
    secrets: Path
    home: Path
    backup_passphrase: str
    number_b: str
    iphone_udid: str
    android_serial: str
    android_key: str | None = None
    maestro: str = "maestro"
    notify: Notify = field(default_factory=Notify)

    def __repr__(self) -> str:  # never the secrets, whatever prints a Kit
        return f"Kit(iphone …{self.iphone_udid[-6:]}, android {self.android_serial}, home {self.home})"

    @property
    def runs(self) -> Path:
        return self.home / "runs"

    @property
    def whatferry_home(self) -> Path:
        """whatferry's folder for the kit: its backups and decrypted copies never mix with anyone's own."""
        return self.home / "whatferry"

    def save_android_key(self, key: str) -> None:
        """Keep a 64-digit key read off the Pixel, so the next template reuses it."""
        if not _KEY.match(key):
            raise KitError("that isn't a 64-digit key (64 hexadecimal characters)")
        text = self.secrets.read_text()
        line = f'android_key = "{key}"'
        if re.search(r"(?m)^android_key\s*=.*$", text):
            text = re.sub(r"(?m)^android_key\s*=.*$", line, text)
        else:
            # Before any [table], so it stays a top-level key.
            head, sep, rest = text.partition("\n[")
            text = f"{head.rstrip()}\n{line}\n" + (f"\n[{rest}" if sep else "")
        tmp = self.secrets.with_name(f".{self.secrets.name}.tmp")
        tmp.write_text(text)
        tmp.chmod(0o600)
        os.replace(tmp, self.secrets)
        self.android_key = key


def load(secrets: Path | None = None, home: Path | None = None, env=os.environ) -> Kit:
    path = (secrets or Path(env.get("WHATFERRY_HARNESS_SECRETS") or DEFAULT_SECRETS)).expanduser()
    root = (home or Path(env.get("WHATFERRY_HARNESS_HOME") or DEFAULT_HOME)).expanduser()
    if not path.is_file():
        raise KitError(f"no secrets file at {path}: see harness/README.md")
    if sys.platform != "win32" and path.stat().st_mode & 0o077:
        raise KitError(f"{path} can be read by others: chmod 600 {path}")
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise KitError(f"{path} isn't valid TOML: {e}") from None
    missing = [k for k in REQUIRED if not data.get(k)]
    if missing:
        raise KitError(f"{path} lacks {', '.join(missing)}")
    key = data.get("android_key")
    if key is not None:
        key = re.sub(r"\s", "", str(key)).lower()
        if not _KEY.match(key):
            raise KitError("android_key must be the 64 characters WhatsApp showed (0-9, a-f)")
    notify = data.get("notify") or {}
    unknown = set(notify) - set(Notify.__dataclass_fields__)
    if unknown:
        raise KitError(f"unknown [notify] settings: {', '.join(sorted(unknown))}")
    return Kit(secrets=path, home=root, backup_passphrase=str(data["backup_passphrase"]),
               number_b=str(data["number_b"]), iphone_udid=str(data["iphone_udid"]),
               android_serial=str(data["android_serial"]), android_key=key,
               maestro=str(data.get("maestro") or "maestro"), notify=Notify(**notify))


def isolate(kit: Kit, env=os.environ) -> None:
    """Point whatferry at the kit's own folder, and away from every other backup on this computer."""
    kit.whatferry_home.mkdir(parents=True, exist_ok=True, mode=0o700)
    env["WHATFERRY_HOME"] = str(kit.whatferry_home)
    env["WHATFERRY_BACKUP_ROOT"] = str(kit.whatferry_home / "backups")
    env["WHATFERRY_BACKUP_PASSPHRASE"] = kit.backup_passphrase
    if kit.android_key:
        env["WHATFERRY_ANDROID_KEY"] = kit.android_key
