"""One folder per run, and one notification per pass, pause or failure.

runs/<date>/ holds state.json (which steps are done, and what they made),
log.txt, screenshots/ (every one taken, numbered), compat/ (the schema
checks and conversion reports), fingerprints/ and the diffs, and
summary.txt, the line the notification sends. Folders are owner-only: the
decrypted copies whatferry makes live in the kit's own whatferry folder.
"""

import json
import os
import smtplib
import sys
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from harness.config import Kit


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Run:
    def __init__(self, folder: Path):
        self.folder = folder
        self.state_path = folder / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.is_file() else {}

    @classmethod
    def new(cls, runs: Path, scenario: str, today: str | None = None) -> "Run":
        runs.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = today or datetime.now().strftime("%Y-%m-%d")
        folder, n = runs / name, 1
        while folder.exists():
            n += 1
            folder = runs / f"{name}-{n}"
        folder.mkdir(mode=0o700)
        run = cls(folder)
        run.state = {"scenario": scenario, "started": _now(), "status": "running", "steps": {}, "ctx": {}}
        run.save()
        return run

    @classmethod
    def latest(cls, runs: Path) -> "Run | None":
        folders = sorted((p for p in runs.glob("*") if (p / "state.json").is_file()),
                         key=lambda p: p.stat().st_mtime) if runs.is_dir() else []
        return cls(folders[-1]) if folders else None

    @property
    def ctx(self) -> dict:
        return self.state.setdefault("ctx", {})

    @property
    def steps(self) -> dict:
        return self.state.setdefault("steps", {})

    def save(self) -> None:
        tmp = self.folder / ".state.json.tmp"
        tmp.write_text(json.dumps(self.state, indent=2, default=str))
        tmp.chmod(0o600)
        os.replace(tmp, self.state_path)

    def mark(self, step: str, status: str, **details) -> None:
        self.steps[step] = {"status": status, "at": _now(), **details}
        self.save()

    def log(self, message: str) -> None:
        line = f"{_now()}  {message}"
        print(line, flush=True)
        with (self.folder / "log.txt").open("a") as f:
            f.write(line + "\n")

    def path(self, *parts: str) -> Path:
        path = self.folder.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        return path

    def screenshot_path(self, label: str) -> Path:
        shots = self.folder / "screenshots"
        n = len(list(shots.glob("*.png"))) + 1 if shots.is_dir() else 1
        return self.path("screenshots", f"{n:02d}-{label}.png")

    def save_json(self, name: str, data) -> Path:
        path = self.path(name)
        path.write_text(json.dumps(data, indent=2, default=str))
        path.chmod(0o600)
        return path

    def finish(self, status: str, summary: str) -> None:
        self.state.update(status=status, finished=_now(), summary=summary)
        self.save()
        (self.folder / "summary.txt").write_text(summary + "\n")


def notify(kit: Kit, title: str, message: str, *, urgent: bool = False, attach: Path | None = None,
           opener=urllib.request.urlopen, smtp=smtplib.SMTP) -> list[str]:
    """Send one notification by every configured way; returns which ones worked. Never raises."""
    sent = []
    n = kit.notify
    if n.ntfy:
        headers = {"Title": title, "Priority": "high" if urgent else "default", "Tags": "iphone,android"}
        body = message.encode()
        if attach and attach.is_file():
            # ntfy takes a file as the body, with the message in a header.
            headers |= {"Filename": attach.name, "Message": message.replace("\n", " ")}
            body = attach.read_bytes()
        try:
            opener(urllib.request.Request(n.ntfy, data=body, headers=headers, method="POST"), timeout=30).close()
            sent.append("ntfy")
        except OSError as e:
            print(f"harness: ntfy failed: {e}", file=sys.stderr)
    if n.mail_to and n.smtp_host:
        mail = EmailMessage()
        mail["Subject"], mail["To"] = title, n.mail_to
        mail["From"] = n.smtp_user or n.mail_to
        mail.set_content(message)
        if attach and attach.is_file():
            mail.add_attachment(attach.read_bytes(), maintype="image", subtype="png", filename=attach.name)
        try:
            with smtp(n.smtp_host, n.smtp_port, timeout=30) as server:
                server.starttls()
                if n.smtp_user:
                    server.login(n.smtp_user, n.smtp_password or "")
                server.send_message(mail)
            sent.append("mail")
        except (OSError, smtplib.SMTPException) as e:
            print(f"harness: mail failed: {e}", file=sys.stderr)
    if not sent:
        print(f"harness: {title}: {message}", file=sys.stderr)
    return sent
