"""The two phones of the kit, and the check that no other phone is connected.

Android goes through adb and Maestro (one YAML flow per WhatsApp screen
family, in flows/). The iPhone goes through whatferry's iphone.py, plus
pymobiledevice3 for its WhatsApp version and, where the phone allows, a
screenshot. Every call names the kit's own phone: nothing here picks "the
connected one".
"""

import asyncio
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from whatferry import adb, iphone

from harness.config import Kit

FLOWS = Path(__file__).parent / "flows"
WHATSAPP = "com.whatsapp"
WHATSAPP_ROOT = adb.WHATSAPP_ROOT
# Permissions WhatsApp asks for after `pm clear`: granted up front, so no flow meets their dialogs.
PERMISSIONS = ("android.permission.READ_CONTACTS", "android.permission.WRITE_CONTACTS",
               "android.permission.POST_NOTIFICATIONS", "android.permission.READ_MEDIA_IMAGES",
               "android.permission.READ_MEDIA_VIDEO", "android.permission.READ_MEDIA_AUDIO",
               "android.permission.RECEIVE_SMS", "android.permission.READ_PHONE_STATE",
               "android.permission.READ_PHONE_NUMBERS", "android.permission.CALL_PHONE")


class DeviceError(Exception):
    """A phone didn't do what the step needs; the message says what."""


class FlowFailed(DeviceError):
    """A Maestro flow met a screen it doesn't know: the harness stops there, never guesses."""

    def __init__(self, flow: str, output: str):
        super().__init__(f"flow {flow} failed: {output.strip().splitlines()[-1] if output.strip() else 'no output'}")
        self.flow, self.output = flow, output


@dataclass
class Connected:
    iphones: list[str]
    androids: list[str]


def connected() -> Connected:
    tool = adb.find_adb()
    androids = [d.serial for d in adb.devices(tool)] if tool else []
    try:
        phones = [p.udid for p in iphone.iphones()]
    except iphone.IphoneError:
        phones = []
    return Connected(phones, androids)


def check_allowed(kit: Kit, found: Connected | None = None) -> None:
    """Refuse to start unless the kit's two phones are there, and no other."""
    found = found or connected()
    strangers = [u for u in found.iphones if u.upper() != kit.iphone_udid.upper()]
    strangers += [s for s in found.androids if s != kit.android_serial]
    if strangers:
        raise DeviceError(f"a phone that isn't the test kit's is connected ({', '.join(strangers)}): unplug it. "
                          "The harness never runs next to another phone")
    if kit.iphone_udid.upper() not in (u.upper() for u in found.iphones):
        raise DeviceError("the test iPhone isn't connected")
    if kit.android_serial not in found.androids:
        raise DeviceError("the test Pixel isn't connected (or USB debugging is off)")


class Android:
    def __init__(self, kit: Kit):
        tool = adb.find_adb()
        if tool is None:
            raise DeviceError("adb isn't installed")
        self.tool, self.serial, self.maestro = tool, kit.android_serial, kit.maestro

    def _adb(self, *args: str, timeout: int = 120, binary: bool = False) -> subprocess.CompletedProcess:
        result = subprocess.run([str(self.tool), "-s", self.serial, *args], capture_output=True, timeout=timeout,
                                text=not binary)
        if result.returncode != 0:
            err = result.stderr if not binary else result.stderr.decode(errors="replace")
            raise DeviceError(f"adb {args[0]} failed: {err.strip() or 'no reason given'}")
        return result

    def shell(self, command: str, timeout: int = 120) -> str:
        return self._adb("shell", command, timeout=timeout).stdout

    def whatsapp_version(self) -> str | None:
        found = re.search(r"versionName=(\S+)", self.shell(f"dumpsys package {WHATSAPP}"))
        return found.group(1) if found else None

    def clear_whatsapp(self) -> None:
        """WhatsApp as just installed: its data, account and backup key gone; the backup files stay."""
        self.shell(f"pm clear {WHATSAPP}")
        for permission in PERMISSIONS:
            subprocess.run([str(self.tool), "-s", self.serial, "shell", "pm", "grant", WHATSAPP, permission],
                           capture_output=True, timeout=30)

    def open_whatsapp(self) -> None:
        self.shell(f"monkey -p {WHATSAPP} -c android.intent.category.LAUNCHER 1")

    def screenshot(self, path: Path) -> Path | None:
        try:
            data = self._adb("exec-out", "screencap", "-p", binary=True).stdout
        except (DeviceError, subprocess.TimeoutExpired):
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def screen_text(self) -> str:
        """Every text on screen, from the accessibility tree."""
        return self._adb("exec-out", "uiautomator", "dump", "/dev/tty").stdout

    def flow(self, name: str, log: Path, **env: str) -> str:
        """Run flows/<name>.yaml; a flow that fails raises FlowFailed with Maestro's output."""
        command = [self.maestro, "--device", self.serial, "test"]
        for key, value in env.items():
            command += ["-e", f"{key}={value}"]
        command.append(str(FLOWS / f"{name}.yaml"))
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        except FileNotFoundError:
            raise DeviceError("Maestro isn't installed: https://maestro.dev") from None
        except subprocess.TimeoutExpired as e:
            raise FlowFailed(name, f"timed out after {e.timeout}s") from None
        output = result.stdout + result.stderr
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(f"\n--- flow {name}\n{output}")
        if result.returncode != 0:
            raise FlowFailed(name, output)
        return output

    def backups(self) -> list[adb.PhoneBackup]:
        return adb.phone_backups(self.tool, self.serial)

    def pull_backup(self, dest: Path) -> Path:
        """The main account's full backup (msgstore.db.crypt15) into dest."""
        found = [b for b in self.backups() if b.usable and b.name == "msgstore.db.crypt15"
                 and b.path.startswith(f"{WHATSAPP_ROOT}/Databases/")]
        if not found:
            raise DeviceError("no msgstore.db.crypt15 on the Pixel: did the backup flow finish?")
        return adb.pull(self.tool, self.serial, found[0].path, dest)

    def pull_media(self, dest: Path) -> Path:
        """WhatsApp's Media folder, which the backup file doesn't hold, for the media hashes."""
        dest.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._adb("pull", f"{WHATSAPP_ROOT}/Media", str(dest), timeout=3600)
        return dest / "Media"

    def push(self, folder: Path) -> dict:
        return adb.push(self.tool, self.serial, WHATSAPP_ROOT, folder)

    def sms_inbox(self) -> str:
        return self.shell("content query --uri content://sms/inbox --projection address:body:date --sort 'date DESC'")


class Iphone:
    def __init__(self, kit: Kit):
        self.udid = kit.iphone_udid

    def phone(self) -> iphone.Iphone:
        return iphone.find(self.udid)

    def wait_until_back(self, timeout: float = 1800, every: float = 15, sleep=time.sleep) -> iphone.Iphone:
        """After a restore the phone restarts: wait until it is paired and answering again."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                return iphone.find(self.udid)
            except iphone.IphoneError:
                if time.monotonic() > deadline:
                    raise DeviceError("the iPhone didn't come back after the restore: is it on the lock screen?")
            sleep(every)

    def whatsapp_version(self) -> str | None:
        try:
            return asyncio.run(_app_version(self.udid, iphone.WHATSAPP_APP))
        except Exception:  # noqa: BLE001 - logged as unknown, never a reason to stop
            return None

    def has_app(self, bundle: str) -> bool:
        return asyncio.run(_app_version(self.udid, bundle, installed_only=True)) is not None

    def remove_app(self, bundle: str) -> None:
        """Delete an app and all its data, as long-press → Remove App → Delete App does."""
        try:
            asyncio.run(_uninstall(self.udid, bundle))
        except Exception as e:  # noqa: BLE001
            raise DeviceError(f"the iPhone wouldn't remove {bundle}: {e}") from e

    def wait_for_app(self, bundle: str, timeout: float = 900, every: float = 10, sleep=time.sleep) -> bool:
        """Whether an app finishes installing (an App Store download) within the timeout."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                if self.has_app(bundle):
                    return True
            except Exception:  # noqa: BLE001 - the phone busy installing
                pass
            if time.monotonic() > deadline:
                return False
            sleep(every)

    def screenshot(self, path: Path) -> Path | None:
        """Where the phone allows one; None otherwise, and the pause says what to do without a picture.

        iOS 17 and later: through pymobiledevice3's tunnel and the developer disk image (Stage 2's
        setup). Older: the lockdown screenshot service.
        """
        from harness.ios_ui import screenshot_over_tunnel

        data = None
        for take in (screenshot_over_tunnel, _screenshot):
            try:
                data = asyncio.run(take(self.udid))
                break
            except Exception:  # noqa: BLE001
                continue
        if data is None:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


async def _app_version(udid: str, bundle: str, installed_only: bool = False) -> str | None:
    """The app's version; with installed_only, "" for an app there without one, None when absent or still a placeholder."""
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.installation_proxy import InstallationProxyService

    lockdown = await create_using_usbmux(serial=udid, autopair=False)
    try:
        async with InstallationProxyService(lockdown) as proxy:
            apps = await proxy.get_apps(bundle_identifiers=[bundle])
        app = apps.get(bundle)
        if app is None:
            return None
        if installed_only and app.get("IsPlaceholder"):
            return None  # an App Store download still under way
        return app.get("CFBundleShortVersionString") or ("" if installed_only else None)
    finally:
        await lockdown.close()


async def _uninstall(udid: str, bundle: str) -> None:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.installation_proxy import InstallationProxyService

    lockdown = await create_using_usbmux(serial=udid, autopair=False)
    try:
        async with InstallationProxyService(lockdown) as proxy:
            await proxy.uninstall(bundle)
    finally:
        await lockdown.close()


async def _screenshot(udid: str) -> bytes:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.screenshot import ScreenshotService

    lockdown = await create_using_usbmux(serial=udid, autopair=False)
    try:
        async with ScreenshotService(lockdown) as service:
            return await service.take_screenshot()
    finally:
        await lockdown.close()
