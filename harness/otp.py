"""WhatsApp's registration code, read from the Pixel's SMS inbox.

B's SIM lives in the Pixel whichever phone B is being registered on, so the
code always arrives there. On the Pixel itself WhatsApp reads it on its own;
for the iPhone the harness reads it here and hands it on.
"""

import re
import time
from dataclasses import dataclass

# "Row: 0 address=WhatsApp, body=Your WhatsApp code: 123-456 …, date=1761480000000"
_ROW = re.compile(r"^Row: \d+ address=(?P<address>.*?), body=(?P<body>.*), date=(?P<date>\d+)\s*$", re.S)
_CODE = re.compile(r"(?<!\d)(\d{3})[- ]?(\d{3})(?!\d)")


@dataclass(frozen=True)
class Sms:
    address: str
    body: str
    date_ms: int


def parse_inbox(text: str) -> list[Sms]:
    """`content query` output, one row per line; a body with a newline continues on the next."""
    rows, current = [], None
    for line in text.splitlines():
        if line.startswith("Row: "):
            if current:
                rows.append(current)
            current = line
        elif current is not None:
            current += "\n" + line
    if current:
        rows.append(current)
    found = []
    for row in rows:
        m = _ROW.match(row)
        if m:
            found.append(Sms(m["address"], m["body"], int(m["date"])))
    return found


def whatsapp_code(messages: list[Sms], since_ms: int) -> str | None:
    """The newest WhatsApp code that arrived after since_ms, as six digits."""
    for sms in sorted(messages, key=lambda s: s.date_ms, reverse=True):
        if sms.date_ms < since_ms or "whatsapp" not in (sms.body + sms.address).lower():
            continue
        m = _CODE.search(sms.body)
        if m:
            return m.group(1) + m.group(2)
    return None


def wait_for_code(android, since_ms: int, timeout: float = 900, every: float = 5, sleep=time.sleep,
                  clock=time.monotonic) -> str | None:
    deadline = clock() + timeout
    while True:
        code = whatsapp_code(parse_inbox(android.sms_inbox()), since_ms)
        if code or clock() > deadline:
            return code
        sleep(every)
