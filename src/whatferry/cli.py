"""whatferry's command line: read-only discovery, Android and iPhone side.

Secrets never go on the command line, where shell history would keep them:
the Android key comes from --key-file, WHATFERRY_ANDROID_KEY or a prompt, and
the iPhone backup passphrase from WHATFERRY_BACKUP_PASSPHRASE or a prompt.
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from whatferry import android, ios, sqlite_summary, workdir
from whatferry.ios_backup import (Backup, BackupError, WrongPassphrase, backup_roots, device_info, find_backup,
                                  list_backups)

HOW_TO_BACK_UP = {
    "darwin": "In Finder: select the iPhone, tick 'Encrypt local backup', then 'Back Up Now'.",
    "win32": "In the Apple Devices app (or iTunes): select the iPhone, tick 'Encrypt local backup', "
             "then 'Back Up Now'.",
}
HOW_TO_BACK_UP_ELSEWHERE = (
    "With libimobiledevice: `idevicebackup2 encryption on` once, then `idevicebackup2 backup --full <folder>`; "
    "set WHATFERRY_BACKUP_ROOT to that folder.")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.run(args)
    except (android.DecryptError, BackupError, FileNotFoundError) as e:
        print(f"whatferry: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="whatferry", description=(
        "Move WhatsApp chats from Android to iPhone. This version only reads: "
        "it decrypts and describes backups, and never writes to a phone or a backup."))
    sides = p.add_subparsers(required=True, metavar="side")

    a = sides.add_parser("android", help="the Android backup").add_subparsers(required=True, metavar="command")
    ai = a.add_parser("inspect", help="decrypt msgstore.db.crypt15 and describe it")
    ai.add_argument("backup", type=Path, help="msgstore.db.crypt15 (or crypt14, or a decrypted msgstore.db)")
    ai.add_argument("--key-file", type=Path,
                    help="file holding the 64-digit key, or a WhatsApp key file from a rooted phone")
    ai.set_defaults(run=_android_inspect)

    i = sides.add_parser("ios", help="the iPhone backup").add_subparsers(required=True, metavar="command")
    ib = i.add_parser("backups", help="list the iPhone backups on this computer")
    ib.set_defaults(run=_ios_backups)
    ii = i.add_parser("inspect", help="map WhatsApp's files and databases in a backup")
    ii.add_argument("backup", help="backup folder, or its name as `whatferry ios backups` lists it")
    ii.set_defaults(run=_ios_inspect)
    idf = i.add_parser("diff", help="which WhatsApp files changed between two backups")
    idf.add_argument("before", help="the earlier backup (folder or name)")
    idf.add_argument("after", help="the later backup (folder or name)")
    idf.set_defaults(run=_ios_diff)
    return p


def _android_inspect(args) -> int:
    report, run = android.inspect(args.backup, _android_key(args))
    _save_report(run, report.as_dict())
    print(f"Android backup: {report.source}")
    if report.header:
        print(f"  made by WhatsApp {report.header.app_version or '?'}, "
              f"number ending in {report.header.number_ends_with or '?'}")
    print(f"  database version {report.user_version}, {report.tables} tables, layout: {report.layout}")
    print(f"  messages from {report.first_message or '?'} to {report.last_message or '?'}")
    _print_counts(report.counts)
    if report.jid_servers:
        print("  contact identifiers by server:")
        for server, n in report.jid_servers.items():
            print(f"    {server:<28} {n:>8}")
    print(f"  {len(report.message_types)} message types in use (counts in report.json)")
    _print_run(run)
    return 0


def _android_key(args):
    if args.key_file:
        return android.load_key(args.key_file)
    with args.backup.open("rb") as f:
        if sqlite_summary.is_sqlite(f.read(16)):
            return None
    text = os.environ.get("WHATFERRY_ANDROID_KEY") or getpass.getpass("64-digit backup key (hidden): ")
    return android.parse_key(text)


def _ios_backups(args) -> int:
    roots = backup_roots()
    backups = list_backups(roots)
    if not backups:
        where = ", ".join(str(r) for r in roots) or "no default folder on this system"
        print(f"No backups found ({where}).")
        print(HOW_TO_BACK_UP.get(sys.platform, HOW_TO_BACK_UP_ELSEWHERE))
        return 0
    for folder, info in backups:
        lock = "encrypted" if info.encrypted else "NOT encrypted"
        print(f"{folder.name}  {info.name or '?'}  {info.model or '?'} iOS {info.ios_version or '?'}  "
              f"{info.backup_date or '?'}  {lock}")
    return 0


def _ios_inspect(args) -> int:
    report, run = ios.inspect(_open_backup(args.backup))
    _save_report(run, report.as_dict())
    d = report.device
    print(f"iPhone backup: {d.name or '?'} ({d.model or '?'}, iOS {d.ios_version or '?'}), made {d.backup_date or '?'}")
    if not d.encrypted:
        print("  NOT encrypted: fine for looking, but writing chats back will need an encrypted backup.")
    if not report.domains:
        print("  No WhatsApp data in this backup.")
    for domain, n in report.domains.items():
        print(f"  {domain}: {n['files']} files, {_size(n['bytes'])}")
        for folder, count in list(report.top_folders[domain].items())[:8]:
            print(f"      {folder}/  {count} files")
    for db in report.databases:
        print(f"  database {db.domain}/{db.path}: version {db.user_version}, {db.tables} tables, {_size(db.size)}")
        if db.counts:
            print(f"      messages from {db.first_message or '?'} to {db.last_message or '?'}")
            _print_counts(db.counts, indent="      ")
    stores = report.chat_storages
    if len(stores) > 1:
        print(f"  {len(stores)} ChatStorage databases: probably one per account (paths above).")
    _print_run(run)
    return 0


def _ios_diff(args) -> int:
    before = _open_backup(args.before)
    after = _open_backup(args.after, passphrase=before.passphrase)
    result = ios.diff(before, after)
    run = workdir.new_run("ios-diff")
    lines = [f"+ {e.domain}/{e.path}" for e in result.added]
    lines += [f"- {e.domain}/{e.path}" for e in result.removed]
    lines += [f"~ {b.domain}/{b.path}  {a.size} -> {b.size} bytes" for a, b in result.changed]
    workdir.write_private(run / "diff.txt", ("\n".join(lines) + "\n").encode())
    print(f"WhatsApp files: {len(result.added)} added, {len(result.removed)} removed, "
          f"{len(result.changed)} changed")
    for folder, counts in result.by_folder().items():
        print(f"  {folder}  " + ", ".join(f"{n} {kind}" for kind, n in counts.items()))
    _print_run(run)
    return 0


def _open_backup(name: str, passphrase: str | None = None) -> Backup:
    """Open a backup by folder or listed name, asking for its passphrase if needed.

    A passphrase that worked on an earlier backup is tried first: two backups
    of the same iPhone share one.
    """
    folder = find_backup(name)
    if not device_info(folder).encrypted:
        return Backup(folder)
    passphrase = passphrase or os.environ.get("WHATFERRY_BACKUP_PASSPHRASE")
    for attempt in range(3):
        if passphrase is None:
            passphrase = getpass.getpass(f"Passphrase for backup {folder.name} (hidden): ")
        try:
            return Backup(folder, passphrase)
        except WrongPassphrase:
            if attempt == 2:
                raise
            print("Wrong passphrase, try again.", file=sys.stderr)
            passphrase = None
    raise AssertionError("unreachable")


def _print_counts(counts: dict, indent: str = "  ") -> None:
    for label, n in counts.items():
        if n is not None:
            print(f"{indent}{label:<30} {n:>8}")


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _save_report(run: Path, report: dict) -> None:
    workdir.write_private(run / "report.json", json.dumps(report, indent=2, default=str).encode())


def _print_run(run: Path) -> None:
    print(f"\nDecrypted copies and report.json are in {run} (readable only by you).")
