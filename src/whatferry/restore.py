"""Putting a backup whatferry wrote back onto the iPhone it came from, over USB.

A restore replaces everything on the phone with what is in the backup, as
Finder's "Restore Backup" does: anything that reached the phone after the
backup was made is gone afterwards. The phone restarts when it's done.

This talks to the phone through pymobiledevice3, which goes through usbmuxd:
Apple's on macOS and Windows (it comes with Finder, and with the Apple
Devices app or iTunes), the usbmuxd package on Linux. Only an iPhone this
computer is already paired with ("Trust This Computer") is used; nothing here
asks to pair. Finding the phone and the restore itself are in iphone.py.

iOS refuses a restore while Find My is on, so that is checked first.
"""

import plistlib
import unicodedata
from pathlib import Path
from typing import Callable

from whatferry import iphone
from whatferry.iphone import Iphone, IphoneError

# Kept under its old name: callers catch RestoreError.
RestoreError = IphoneError

__all__ = ["Iphone", "RestoreError", "backup_udid", "iphones", "restore", "same_name"]


def iphones() -> list[Iphone]:
    """The iPhones connected by cable; nothing here asks one to pair."""
    return iphone.iphones(autopair=False)


def same_name(typed: str, name: str) -> bool:
    """Whether a typed phone name is the phone's: iOS names have a curly ’ ("Anna’s iPhone") keyboards don't type."""
    def plain(s: str) -> str:
        return unicodedata.normalize("NFKC", s).replace("’", "'").replace("‘", "'").strip().casefold()
    return plain(typed) == plain(name)


def backup_udid(folder: Path) -> str:
    """The iPhone a backup belongs to: its folder name, as Finder names it."""
    if not (folder / "Manifest.plist").is_file() or not (folder / "Info.plist").is_file():
        raise RestoreError(f"{folder} isn't an iPhone backup")
    if iphone.is_whatsapp_only(folder):
        raise RestoreError(f"{folder.name} is a WhatsApp-only backup: it holds nothing else of the phone, so it is "
                           "never restored")
    info = plistlib.loads((folder / "Info.plist").read_bytes())
    target = info.get("Target Identifier") or info.get("Unique Identifier")
    if target and target.upper() != folder.name.upper():
        raise RestoreError(f"{folder.name} is the backup of another iPhone ({target})")
    return folder.name


def restore(folder: Path, passphrase: str | None, progress: Callable[[float], None] = lambda _: None) -> Iphone:
    """Restore a backup onto its own iPhone, which must be connected, paired, and have Find My off."""
    udid = backup_udid(folder)
    encrypted = plistlib.loads((folder / "Manifest.plist").read_bytes()).get("IsEncrypted", False)
    if encrypted and not passphrase:
        # pymobiledevice3 would only log this and return as if it had worked.
        raise RestoreError("this backup is encrypted: its passphrase is needed to restore it")
    phone = next((p for p in iphones() if p.udid.upper() == udid.upper()), None)
    if phone is None:
        raise RestoreError(f"connect the iPhone this backup is from (…{udid[-6:]}) with a cable, and unlock it")
    if not phone.paired:
        raise RestoreError("this computer isn't trusted by the iPhone yet: unlock it, connect it, and tap Trust")
    if phone.find_my:
        raise RestoreError("Find My is on: turn it off on the iPhone (Settings → your name → Find My → "
                           "Find My iPhone), then try again")
    if phone.find_my is None:
        raise RestoreError("the iPhone didn't say whether Find My is off: unlock it, keep it on the home screen, "
                           "and try again")
    iphone.restore(folder, udid, passphrase or "", progress)
    return phone
