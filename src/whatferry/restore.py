"""Putting a backup whatferry wrote back onto the iPhone it came from, over USB.

A restore replaces everything on the phone with what is in the backup, as
Finder's "Restore Backup" does: anything that reached the phone after the
backup was made is gone afterwards. The phone restarts when it's done.

This talks to the phone through pymobiledevice3, which goes through usbmuxd:
Apple's on macOS and Windows (it comes with Finder, and with the Apple
Devices app or iTunes), the usbmuxd package on Linux. Only an iPhone this
computer is already paired with ("Trust This Computer") is used; nothing here
asks to pair.

iOS refuses a restore while Find My is on, so that is checked first.
"""

import asyncio
import plistlib
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


class RestoreError(Exception):
    """A restore can't start or didn't finish; the message says why."""


@dataclass
class Iphone:
    udid: str
    name: str | None
    ios_version: str | None
    # Paired with this computer: needed for a restore.
    paired: bool
    # None when the phone wouldn't say (not paired, or locked).
    find_my: bool | None

    def as_dict(self) -> dict:
        return asdict(self)


def iphones() -> list[Iphone]:
    """The iPhones connected by cable."""
    try:
        return asyncio.run(_list())
    except RestoreError:
        raise
    except Exception as e:  # noqa: BLE001 - usbmuxd missing, a phone unplugged mid-way, ...
        raise RestoreError(f"can't reach connected iPhones: {e}. On Windows, install Apple Devices (or iTunes); "
                           "on Linux, the usbmuxd package") from e


def same_name(typed: str, name: str) -> bool:
    """Whether a typed phone name is the phone's: iOS names have a curly ’ ("Anna’s iPhone") keyboards don't type."""
    def plain(s: str) -> str:
        return unicodedata.normalize("NFKC", s).replace("’", "'").replace("‘", "'").strip().casefold()
    return plain(typed) == plain(name)


def backup_udid(folder: Path) -> str:
    """The iPhone a backup belongs to: its folder name, as Finder names it."""
    if not (folder / "Manifest.plist").is_file() or not (folder / "Info.plist").is_file():
        raise RestoreError(f"{folder} isn't an iPhone backup")
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
    try:
        asyncio.run(_restore(folder.parent, udid, passphrase or "", progress))
    except Exception as e:  # noqa: BLE001 - the phone's own reason, passed on
        raise RestoreError(f"the iPhone stopped the restore: {e}") from e
    return phone


# The two places that talk to the phone, kept apart so tests can stand in for it.

async def _list() -> list[Iphone]:
    from pymobiledevice3 import usbmux
    from pymobiledevice3.lockdown import create_using_usbmux

    found = []
    for device in await usbmux.list_devices():
        if device.connection_type != "USB":
            continue
        try:
            lockdown = await create_using_usbmux(serial=device.serial, autopair=False)
        except Exception:  # noqa: BLE001 - locked, or never trusted: listed, not usable
            found.append(Iphone(device.serial, None, None, False, None))
            continue
        try:
            try:
                find_my = await lockdown.get_value(domain="com.apple.fmip", key="IsAssociated")
            except Exception:  # noqa: BLE001
                find_my = None
            found.append(Iphone(lockdown.udid, lockdown.all_values.get("DeviceName"), lockdown.product_version,
                                bool(lockdown.paired), None if find_my is None else bool(find_my)))
        finally:
            await lockdown.close()
    return found


async def _restore(backups: Path, udid: str, passphrase: str, progress: Callable[[float], None]) -> None:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

    lockdown = await create_using_usbmux(serial=udid, autopair=False)
    try:
        async with Mobilebackup2Service(lockdown) as service:
            # Everything, as Finder restores: system files and settings too.
            # The backup was made from this phone shortly before, so that is
            # the phone as it was then, with the converted chats added.
            await service.restore(backup_directory=backups, source=udid, system=True, settings=True, reboot=True,
                                  copy=False, remove=False, password=passphrase, progress_callback=progress)
    finally:
        await lockdown.close()
