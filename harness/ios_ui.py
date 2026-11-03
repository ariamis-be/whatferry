"""The iPhone's taps, Stage 2: WebDriverAgent driven through pymobiledevice3.

Maestro can't drive a physical iPhone, so the harness talks to WebDriverAgent
(WDA) itself. WDA is the XCUITest runner app Appium uses; the kit builds it
once, signed with the paid developer account (harness/README.md). Opening a
session gets the phone ready first, because a restore undoes most of it:

1. Developer Mode: turned back on if the restore turned it off. With no
   passcode set, pymobiledevice3 can do that alone; the phone restarts.
2. The developer disk image, mounted again after every restart.
3. The WDA runner app, installed again from the kit's signed copy: a
   restore leaves developer-signed apps out.
4. The runner started through pymobiledevice3's tunnel (`sudo
   pymobiledevice3 remote tunneld`, which iOS 17 and later need), then a
   WDA session over the USB connection, no port forwarding.

A screen is read through WDA's accessibility tree and matched by label or
name, case-insensitive regular expressions matched whole (NSPredicate
MATCHES). An expected screen that doesn't come raises ScreenUnknown, and
the step falls back to a Stage 1 pause; the harness never guesses.
"""

import asyncio
import re
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

WDA_RUNNER = "com.facebook.WebDriverAgentRunner.xctrunner"
WDA_PORT = 8100


class UiUnavailable(Exception):
    """WDA can't be reached: the message says what is missing. The step pauses for a person instead."""


class ScreenUnknown(Exception):
    """The phone isn't on the screen the step expects."""


@dataclass
class Element:
    type: str
    label: str
    name: str
    value: str
    visible: bool


def elements(source: str) -> list[Element]:
    """Every element of a WDA source tree, in screen order."""
    try:
        root = ElementTree.fromstring(source)
    except ElementTree.ParseError:
        return []
    return [Element(e.tag, e.get("label") or "", e.get("name") or "", e.get("value") or "",
                    e.get("visible", "true") == "true") for e in root.iter()]


def _matches(pattern: str, element: Element) -> bool:
    return element.visible and any(re.fullmatch(pattern, s, re.I | re.S)
                                   for s in (element.label, element.name) if s)


def _predicate(pattern: str) -> str:
    quoted = pattern.replace("\\", "\\\\").replace("'", "\\'")
    return f"(label MATCHES[c] '{quoted}' OR name MATCHES[c] '{quoted}') AND visible == 1"


class Screen:
    """What a step does on the iPhone: wait for, tap, type, launch. One WDA session."""

    def __init__(self, client, log=print, clock=time.monotonic, sleep=asyncio.sleep, every: float = 1.0):
        self.client, self.log, self.clock, self.sleep, self.every = client, log, clock, sleep, every

    async def source(self) -> str:
        return await self.client.get_source(self.client.session_id)

    async def visible(self, pattern: str) -> bool:
        return any(_matches(pattern, e) for e in elements(await self.source()))

    async def wait(self, pattern: str, timeout: float = 30) -> None:
        deadline = self.clock() + timeout
        while not await self.visible(pattern):
            if self.clock() > deadline:
                raise ScreenUnknown(f"waited {timeout:.0f}s for “{pattern}” on the iPhone")
            await self.sleep(self.every)

    async def which(self, patterns: dict[str, str], timeout: float = 30) -> str:
        """The first of several screens to show up, by its key."""
        deadline = self.clock() + timeout
        while True:
            found = elements(await self.source())
            for key, pattern in patterns.items():
                if any(_matches(pattern, e) for e in found):
                    return key
            if self.clock() > deadline:
                raise ScreenUnknown(f"none of {', '.join(patterns)} showed on the iPhone within {timeout:.0f}s")
            await self.sleep(self.every)

    async def tap(self, pattern: str, timeout: float = 30) -> None:
        await self.wait(pattern, timeout)
        self.log(f"  iPhone: tap “{pattern}”")
        element = await self.client.find_element("predicate string", _predicate(pattern))
        await self.client.click(element)

    async def tap_if(self, pattern: str) -> bool:
        if await self.visible(pattern):
            await self.tap(pattern, timeout=0)
            return True
        return False

    async def fill(self, index: int, text: str, kind: str = "XCUIElementTypeTextField") -> None:
        """Type into the index-th text field of the screen, replacing what it holds."""
        fields = [e for e in elements(await self.source()) if e.type == kind and e.visible]
        if len(fields) <= index:
            raise ScreenUnknown(f"expected at least {index + 1} text fields on the iPhone, found {len(fields)}")
        element = await self.client.find_element("class chain", f"**/{kind}[`visible == 1`][{index + 1}]")
        session = self.client.session_id
        with suppress(Exception):  # an empty field can't be cleared on some iOS versions
            await self.client._request_json("POST", f"/session/{session}/element/{element}/clear", {})
        await self.client._request_json("POST", f"/session/{session}/element/{element}/value",
                                        {"value": list(text), "text": text})

    async def type(self, text: str) -> None:
        await self.client.send_keys(text, self.client.session_id)

    async def launch(self, bundle: str) -> None:
        """Open an app in front, in a new WDA session attached to it."""
        self.log(f"  iPhone: open {bundle}")
        await self.client.start_session(bundle_id=bundle)

    async def home(self) -> None:
        await self.client.press_button("home", self.client.session_id)

    async def screenshot(self) -> bytes:
        return await self.client.get_screenshot(self.client.session_id)


@asynccontextmanager
async def session(udid: str, wda_app: Path | None, runner: str = WDA_RUNNER, log=print):
    """A Screen on the iPhone, its Developer Mode, disk image and WDA made ready first."""
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.amfi import AmfiService
    from pymobiledevice3.services.installation_proxy import InstallationProxyService
    from pymobiledevice3.services.mobile_image_mounter import auto_mount
    from pymobiledevice3.services.wda import WdaServiceClient
    from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid

    lockdown = await create_using_usbmux(serial=udid, autopair=False)
    rsd, runner_task = None, None
    try:
        if lockdown.has_developer_mode and not await lockdown.get_developer_mode_status():
            log("  iPhone: Developer Mode is off (after a restore?): turning it on, the iPhone restarts")
            try:
                await AmfiService(lockdown).enable_developer_mode(enable_post_restart=True)
            except Exception as e:  # noqa: BLE001 - a passcode, or AMFI's own refusal
                raise UiUnavailable(f"Developer Mode couldn't be turned on: {e}") from e
            await lockdown.close()
            lockdown = await create_using_usbmux(serial=udid, autopair=False)
        try:
            await auto_mount(lockdown)
        except Exception as e:  # noqa: BLE001
            if "already mounted" not in str(e).lower() and type(e).__name__ != "AlreadyMountedError":
                raise UiUnavailable(f"the developer disk image didn't mount: {e}") from e
        async with InstallationProxyService(lockdown) as proxy:
            if runner not in await proxy.get_apps(bundle_identifiers=[runner]):
                if not wda_app or not Path(wda_app).exists():
                    raise UiUnavailable(f"WebDriverAgent ({runner}) isn't on the iPhone and the kit has no wda_app "
                                        "to install it from")
                log("  iPhone: installing WebDriverAgent again")
                await proxy.install_from_local(Path(wda_app), developer=True)
        try:
            rsd = await get_tunneld_device_by_udid(udid)
        except Exception as e:  # noqa: BLE001 - tunneld not running
            raise UiUnavailable(f"pymobiledevice3's tunnel isn't running (sudo pymobiledevice3 remote tunneld): {e}") \
                from e
        if rsd is None:
            raise UiUnavailable("pymobiledevice3's tunnel has no connection to the iPhone yet")
        runner_task = await _start_runner(rsd, runner)
        client = WdaServiceClient(service_provider=rsd, timeout=30)
        await client.start_session()
        yield Screen(client, log)
    finally:
        if runner_task is not None:
            runner_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await runner_task
        if rsd is not None:
            with suppress(Exception):
                await rsd.close()
        with suppress(Exception):
            await lockdown.close()


async def _start_runner(rsd, runner: str, timeout: float = 60) -> asyncio.Task:
    """Start the WDA runner app as an XCUITest, and wait until its HTTP server answers."""
    from pymobiledevice3 import usbmux
    from pymobiledevice3.services.dvt.testmanaged.xcuitest import TestConfig, XCUITestService

    cfg = await TestConfig.create_for(rsd, runner_bundle_id=runner)
    task = asyncio.create_task(XCUITestService(rsd).run(cfg), name="wda-runner")
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if task.done():
            task.result()
            raise UiUnavailable("WebDriverAgent stopped before it answered")
        if asyncio.get_running_loop().time() > deadline:
            task.cancel()
            raise UiUnavailable(f"WebDriverAgent didn't answer within {timeout:.0f}s")
        device = await usbmux.select_device(rsd.udid)
        if device is not None:
            try:
                sock = await device.connect(WDA_PORT)
            except Exception:  # noqa: BLE001 - not listening yet
                await asyncio.sleep(0.5)
                continue
            sock.close()
            return task
        await asyncio.sleep(0.5)


async def facts(udid: str) -> dict:
    """What preflight logs about Stage 2: Developer Mode, supervision, the tunnel."""
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.mobile_config import MobileConfigService
    from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid

    out = {}
    lockdown = await create_using_usbmux(serial=udid, autopair=False)
    try:
        with suppress(Exception):
            out["developer_mode"] = bool(await lockdown.get_developer_mode_status())
        with suppress(Exception):
            async with MobileConfigService(lockdown) as config:
                out["supervised"] = bool(((await config.get_cloud_configuration()) or {}).get("IsSupervised"))
    finally:
        await lockdown.close()
    try:
        rsd = await get_tunneld_device_by_udid(udid)
        out["tunnel"] = rsd is not None
        if rsd is not None:
            await rsd.close()
    except Exception:  # noqa: BLE001
        out["tunnel"] = False
    return out


async def screenshot_over_tunnel(udid: str) -> bytes:
    """A screenshot through the instruments service (iOS 17 and later), which needs the tunnel and disk image."""
    from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
    from pymobiledevice3.services.dvt.instruments.screenshot import Screenshot
    from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid

    rsd = await get_tunneld_device_by_udid(udid)
    if rsd is None:
        raise UiUnavailable("no tunnel to the iPhone")
    try:
        async with DvtProvider(rsd) as dvt, Screenshot(dvt) as shot:
            return await shot.get_screenshot()
    finally:
        await rsd.close()
