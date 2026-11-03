"""The three iPhone pauses of Stage 1, as taps (Stage 2).

Each function does what its pause asks a person to do, through a Screen
(ios_ui.py). Labels are WhatsApp for iOS's and iOS's own, in English, as
regular expressions matched whole and case-insensitively. They are written
from the apps' wording and still have to meet the real phone: a label that
differs raises ScreenUnknown, and the step falls back to its pause, with a
screenshot of where it stopped.
"""

import asyncio
import re

from harness.ios_ui import ScreenUnknown

WHATSAPP = "net.whatsapp.WhatsApp"

SETTINGS_TAB = "Settings|You"
ACCOUNTS = "Accounts?|Account list|Switch accounts?|Manage accounts"
CHAT_LIST = "Chats"
CONTINUE = "Continue|OK|Done|Next|Not Now|Later|Skip|Dismiss|Set Up Later|Allow|Don.t Allow"

# Panes iOS shows after a restore, all answered without signing anything.
SPRINGBOARD_PANES = "Continue|Not Now|Set Up Later.*|Later|Skip|Dismiss|OK|Done"
# What only a person can answer: the harness stops there.
NEEDS_PERSON = ".*Apple Account.*Password.*|Enter.*Password|.*Sign In to Apple Account.*|Verification Code|" \
               "Two-Factor Authentication|Enter Passcode"


def b_label(number: str) -> str:
    """How the accounts list names B: by its profile name ("B", as the harness registers it) or its last digits."""
    last = re.sub(r"\D", "", number)[-4:]
    return f"B|.*{last}.*"


async def _open_settings(s) -> None:
    await s.launch(WHATSAPP)
    await s.tap(SETTINGS_TAB, timeout=60)


async def remove_b(s, c, wait_for_code=None) -> None:
    """WhatsApp → Settings → accounts → B → Remove account, data deleted from this iPhone."""
    await _open_settings(s)
    await s.tap(ACCOUNTS)
    await s.tap(b_label(c.kit.number_b))
    await s.tap(".*Remove account.*|.*Delete account data.*|Remove")
    # The confirmation: remove, and delete its data from this iPhone.
    await s.tap_if(".*Delete.*data.*|Remove|Delete")
    await s.tap_if("Remove|Delete")
    await s.wait(SETTINGS_TAB + "|" + CHAT_LIST, timeout=60)


async def add_b(s, c, wait_for_code) -> None:
    """WhatsApp → Settings → Add account → B's number → the code from the Pixel → profile "B"."""
    from harness.scenarios import split_number

    country, number = split_number(c.kit.number_b)
    await _open_settings(s)
    await s.tap_if(ACCOUNTS)
    await s.tap(".*Add account.*")
    await s.tap_if("Agree (and|&) Continue")
    await s.wait(".*phone number.*", timeout=60)
    since = c.now_ms()
    await s.fill(0, f"+{country}")
    await s.fill(1, number)
    await s.tap("Done|Next")
    await s.tap_if("Yes|OK|Continue")
    await s.wait(".*code.*", timeout=120)
    code = await asyncio.to_thread(wait_for_code, c.android, since)  # the runner keeps running meanwhile
    if not code:
        raise ScreenUnknown("no WhatsApp code reached the Pixel")
    c.log("  iPhone: typing B's code")
    await s.type(code)
    await s.wait(".*Profile info.*|.*Your name.*|.*Restore.*", timeout=300)
    await s.tap_if("Skip|Not Now")
    await s.fill(0, "B")
    await s.tap("Done|Next")
    for _ in range(3):  # notifications, contacts, backups: each "not now"
        if not await s.tap_if(CONTINUE):
            break
    await s.wait(CHAT_LIST, timeout=120)


async def after_restore(s, c, wait_for_code=None) -> None:
    """Past iOS's panes after the restore, then WhatsApp open on B with its chats."""
    for _ in range(12):
        found = await s.which({"person": NEEDS_PERSON, "pane": SPRINGBOARD_PANES, "home": "WhatsApp"},
                              timeout=120)
        if found == "person":
            raise ScreenUnknown("the iPhone asks for the Apple Account: a person signs in")
        if found == "home":
            break
        await s.tap(SPRINGBOARD_PANES, timeout=0)
    await s.launch(WHATSAPP)
    for _ in range(4):  # "restoring media", notifications and the like
        if not await s.tap_if(CONTINUE):
            break
    await s.tap(SETTINGS_TAB, timeout=180)
    await s.tap_if(ACCOUNTS)
    await s.tap(b_label(c.kit.number_b))
    await s.tap(CHAT_LIST, timeout=60)
    await s.wait(CHAT_LIST, timeout=600)
