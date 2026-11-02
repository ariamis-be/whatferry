"""The iPhone over USB: finding it, its backup encryption, backups and restores.

Finder, the Apple Devices app, idevicebackup2 and this are all clients of the
same service on the phone (com.apple.mobilebackup2), so a backup made here is
the one Finder makes: a <udid> folder of Manifest.db, Manifest.plist,
Info.plist, Status.plist and files under two-hex-character folders. They go
in whatferry's own folder (<home>/backups), which `ios backups` and the rest
list next to Finder's; no Full Disk Access is needed to read them.

Everything goes through pymobiledevice3 and usbmuxd: Apple's on macOS and
Windows (with Finder, the Apple Devices app or iTunes), the usbmuxd package on
Linux. The functions that talk to the phone are the underscored ones at the
end, kept apart so tests can stand in for them.
"""

import asyncio
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from whatferry import workdir
from whatferry.ios_backup import Backup, WrongPassphrase, device_info

# The two containers a WhatsApp-only backup keeps: the app's own, and the
# shared group that holds every account's chats and media.
WHATSAPP_ONLY_DOMAINS = ("AppDomain-net.whatsapp.WhatsApp", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared")
WHATSAPP_APP = "net.whatsapp.WhatsApp"
WHATSAPP_GROUP = "group.net.whatsapp.WhatsApp.shared"
# A WhatsApp-only backup sits next to the full one, under this suffix: the
# folder name is not the phone's, so a restore refuses it.
WHATSAPP_ONLY_SUFFIX = "-whatsapp"


class IphoneError(Exception):
    """The iPhone can't be reached, or refused; the message says why."""


@dataclass
class Iphone:
    udid: str
    name: str | None
    ios_version: str | None
    # Paired with this computer ("Trust This Computer"): needed for anything.
    paired: bool
    # None when the phone wouldn't say (not paired, or locked).
    find_my: bool | None

    def as_dict(self) -> dict:
        return asdict(self)


def iphones(autopair: bool = False) -> list[Iphone]:
    """The iPhones connected by cable; with autopair, an unpaired one is asked to trust this computer."""
    try:
        return asyncio.run(_list(autopair))
    except IphoneError:
        raise
    except Exception as e:  # noqa: BLE001 - usbmuxd missing, a phone unplugged mid-way, ...
        raise IphoneError(f"can't reach connected iPhones: {e}. On Windows, install Apple Devices (or iTunes); "
                          "on Linux, the usbmuxd package") from e


def find(udid: str | None = None, autopair: bool = False) -> Iphone:
    """The one connected, paired iPhone (or the one with this UDID)."""
    phones = iphones(autopair)
    if udid:
        phones = [p for p in phones if p.udid.upper() == udid.upper()]
        if not phones:
            raise IphoneError(f"no iPhone …{udid[-6:]} connected: connect it with a cable and unlock it")
    if not phones:
        raise IphoneError("no iPhone connected: connect it with a cable and unlock it")
    if len(phones) > 1:
        raise IphoneError("more than one iPhone connected: choose one with --udid "
                          f"({', '.join(p.udid for p in phones)})")
    phone = phones[0]
    if not phone.paired:
        raise IphoneError("this computer isn't trusted by the iPhone yet: unlock it, tap Trust, and try again")
    return phone


def backups_root() -> Path:
    """Where whatferry's own backups go: one <udid> folder per phone, as Finder lays them out."""
    return workdir.home() / "backups"


def encrypts(phone: Iphone) -> bool:
    """Whether the phone encrypts its backups: the setting Finder's "Encrypt local backup" box shows."""
    return _call("read the backup setting", _will_encrypt(phone.udid))


def turn_on_encryption(phone: Iphone, passphrase: str) -> None:
    """Make the phone encrypt every backup from now on, with this passphrase (Finder shows the box ticked)."""
    if not passphrase:
        raise IphoneError("an empty passphrase can't encrypt a backup")
    _call("turn on backup encryption", _change_password(phone.udid, passphrase))


def backup(phone: Iphone, passphrase: str | None, *, full: bool = False, whatsapp_only: bool = False,
           progress: Callable[[float], None] = lambda _: None) -> Path:
    """Back the phone up into <home>/backups and return the backup folder.

    Incremental into the folder of the last backup, as Finder does, unless
    `full`. A WhatsApp-only backup keeps just WhatsApp's two containers: it
    takes seconds, is always full, needs the passphrase when the phone
    encrypts, and goes into <udid>-whatsapp, which can never be restored.

    The phone can't say whether a passphrase is its own, so an encrypted
    backup is opened with it afterwards; a wrong one is reported and the
    backup is kept.
    """
    root = backups_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    workdir.home().chmod(0o700)
    root.chmod(0o700)
    if whatsapp_only:
        target = root / f"{phone.udid}{WHATSAPP_ONLY_SUFFIX}"
        # The phone writes into <folder>/<udid>: a fresh folder, moved in place once complete.
        staging = root / f".{phone.udid}{WHATSAPP_ONLY_SUFFIX}.partial"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(mode=0o700)
        try:
            _call("make the backup", _backup(staging, phone.udid, True, passphrase or "", progress, True))
            shutil.rmtree(target, ignore_errors=True)
            os.replace(staging / phone.udid, target)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    else:
        target = root / phone.udid
        if not full and passphrase and _encrypted(target):
            # An hour-long backup is not started with a passphrase that doesn't open the last one.
            try:
                Backup(target, passphrase)
            except WrongPassphrase:
                raise IphoneError(f"that passphrase doesn't open the last backup in {target}. If the phone's "
                                  "passphrase changed since, make a full backup instead") from None
        _call("make the backup", _backup(root, phone.udid, full, passphrase or "", progress, False))
    if passphrase and _encrypted(target):
        try:
            Backup(target, passphrase)
        except WrongPassphrase:
            raise IphoneError(f"the backup is made and kept in {target}, but the passphrase given doesn't open "
                              "it: it is the phone's backup passphrase that is needed") from None
    return target


def is_whatsapp_only(folder: Path) -> bool:
    return folder.name.endswith(WHATSAPP_ONLY_SUFFIX)


def restore(folder: Path, udid: str, passphrase: str, progress: Callable[[float], None] = lambda _: None) -> None:
    """Restore the backup in `folder` onto the phone. No checks: restore.restore() makes them first."""
    _call("restore", _restore(folder.parent, udid, passphrase, progress), prefix="the iPhone stopped the restore")


def whatsapp_filter(containers: list[str]) -> Callable:
    """Which files a WhatsApp-only backup keeps.

    While the phone sends files, each comes with its path on the phone, and
    only payloads inside WhatsApp's containers are stored; afterwards
    Manifest.db is pruned to the two domains and anything else is deleted.
    When a path can't be placed (the containers unknown), the file is kept:
    the pruning removes it anyway, and a WhatsApp file is never dropped.
    """
    roots = [c.removeprefix("/private").rstrip("/") for c in containers if c]

    def keep(file) -> bool:
        if file.domain is not None:
            return file.domain in WHATSAPP_ONLY_DOMAINS
        name = (file.device_name or "").removeprefix("/private")
        if not name or not roots:
            return True
        return (any(name == r or name.startswith(r + "/") for r in roots)
                or any(d in name for d in WHATSAPP_ONLY_DOMAINS) or "whatsapp" in name.lower())

    return keep


def _encrypted(folder: Path) -> bool:
    return (folder / "Manifest.db").is_file() and device_info(folder).encrypted


def _call(what: str, coroutine, prefix: str | None = None):
    try:
        return asyncio.run(coroutine)
    except IphoneError:
        raise
    except Exception as e:  # noqa: BLE001 - the phone's own reason, passed on
        raise IphoneError(f"{prefix or f'could not {what}'}: {e}") from e


class _PrivateTempfile:
    """pymobiledevice3 decrypts Manifest.db, the list of every file on the phone,
    into the system's shared temporary folder when it prunes a WhatsApp-only
    backup; sent to whatferry's private folder instead. Kept open-able by name
    on Windows too (delete_on_close=False), which the pruning needs."""

    @staticmethod
    def NamedTemporaryFile(suffix: str = ""):  # noqa: N802 - the name the library calls
        return tempfile.NamedTemporaryFile(suffix=suffix, dir=workdir.private_temp(), delete_on_close=False)


# The places that talk to the phone, kept apart so tests can stand in for it.

async def _lockdown(udid: str, autopair: bool = False):
    from pymobiledevice3.lockdown import create_using_usbmux

    return await create_using_usbmux(serial=udid, autopair=autopair)


async def _list(autopair: bool = False) -> list[Iphone]:
    from pymobiledevice3 import usbmux
    from pymobiledevice3.lockdown import create_using_usbmux

    found = []
    for device in await usbmux.list_devices():
        if device.connection_type != "USB":
            continue
        try:
            lockdown = await create_using_usbmux(serial=device.serial, autopair=autopair)
        except Exception:  # noqa: BLE001 - locked, never trusted, Trust not tapped yet: listed, not usable
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


async def _will_encrypt(udid: str) -> bool:
    from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

    lockdown = await _lockdown(udid)
    try:
        async with Mobilebackup2Service(lockdown) as service:
            return await service.get_will_encrypt()
    finally:
        await lockdown.close()


async def _change_password(udid: str, new: str) -> None:
    from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

    lockdown = await _lockdown(udid)
    try:
        async with Mobilebackup2Service(lockdown) as service:
            # The device link wants a folder; nothing is written to it.
            folder = workdir.private_temp()
            await service.change_password(backup_directory=folder, new=new)
    finally:
        await lockdown.close()


async def _containers(lockdown) -> list[str]:
    """WhatsApp's app and shared-group containers on the phone, or [] if it won't say."""
    from pymobiledevice3.services.installation_proxy import InstallationProxyService

    try:
        async with InstallationProxyService(lockdown) as proxy:
            apps = await proxy.browse(options={"BundleIDs": [WHATSAPP_APP]},
                                      attributes=["CFBundleIdentifier", "Container", "GroupContainers"])
    except Exception:  # noqa: BLE001 - the filter then keeps everything until the pruning
        return []
    found = []
    for app in apps:
        if app.get("CFBundleIdentifier") != WHATSAPP_APP:
            continue
        if app.get("Container"):
            found.append(app["Container"])
        group = (app.get("GroupContainers") or {}).get(WHATSAPP_GROUP)
        if group:
            found.append(group)
    return found


async def _backup(folder: Path, udid: str, full: bool, passphrase: str, progress: Callable[[float], None],
                  whatsapp_only: bool) -> None:
    from pymobiledevice3.services import mobilebackup2
    from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

    mobilebackup2.tempfile = _PrivateTempfile
    lockdown = await _lockdown(udid, autopair=True)
    try:
        filter_callback = whatsapp_filter(await _containers(lockdown)) if whatsapp_only else None
        async with Mobilebackup2Service(lockdown) as service:
            await service.backup(full=full, backup_directory=folder, progress_callback=progress,
                                 filter_callback=filter_callback, password=passphrase,
                                 patch_manifest=whatsapp_only)
    finally:
        await lockdown.close()


async def _restore(backups: Path, udid: str, passphrase: str, progress: Callable[[float], None]) -> None:
    from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

    lockdown = await _lockdown(udid)
    try:
        async with Mobilebackup2Service(lockdown) as service:
            # Everything, as Finder restores: system files and settings too.
            # The backup was made from this phone shortly before, so that is
            # the phone as it was then, with the converted chats added.
            await service.restore(backup_directory=backups, source=udid, system=True, settings=True, reboot=True,
                                  copy=False, remove=False, password=passphrase, progress_callback=progress)
    finally:
        await lockdown.close()
