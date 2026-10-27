"""whatferry's command line: discovery, conversion, writing the new backup, and restoring it.

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

from whatferry import adb, android, backup_writer, convert, ios, restore, sqlite_summary, workdir
from whatferry.ios_backup import (Backup, BackupError, WrongPassphrase, backup_roots, device_info, find_backup,
                                  how_to_back_up, list_backups)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.run(args)
    except (android.DecryptError, BackupError, adb.AdbError, convert.ConvertError, backup_writer.WriteError,
            restore.RestoreError, FileNotFoundError) as e:
        print(f"whatferry: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="whatferry", description=(
        "Move WhatsApp chats from Android to iPhone: decrypt and describe both backups, convert the "
        "chats, write them into a new copy of the iPhone backup, and restore that onto the iPhone."))
    sides = p.add_subparsers(required=True, metavar="command")

    a = sides.add_parser("android", help="the Android backup").add_subparsers(required=True, metavar="command")
    ai = a.add_parser("inspect", help="decrypt msgstore.db.crypt15 and describe it")
    ai.add_argument("backup", type=Path, help="msgstore.db.crypt15 (or crypt14, or a decrypted msgstore.db)")
    ai.add_argument("--key-file", type=Path,
                    help="file holding the 64-digit key, or a WhatsApp key file from a rooted phone")
    ai.set_defaults(run=_android_inspect)
    ap = a.add_parser("phone", help="list phones connected with USB debugging, and their WhatsApp backups")
    ap.set_defaults(run=_android_phone)
    al = a.add_parser("pull", help="copy WhatsApp backups off a phone connected with USB debugging")
    al.add_argument("path", nargs="?", help="a backup path from `whatferry android phone` (default: every "
                                            "usable full backup, one per account)")
    al.add_argument("--serial", help="which phone, when more than one is connected")
    al.add_argument("--to", type=Path, help=f"folder to copy into (default: {adb.default_destination()})")
    al.set_defaults(run=_android_pull)

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
    iw = i.add_parser("write", help="put a `whatferry convert` result into a copy of a backup")
    iw.add_argument("backup", help="the backup the conversion was made from (folder or name)")
    iw.add_argument("convert_run", type=Path, help="the run folder `whatferry convert` printed")
    iw.add_argument("--account-folder", help="data/<id> folder of a second iPhone account (omit for the main one)")
    iw.add_argument("--to", type=Path, help="where to write the new backup folder (default: a private run folder)")
    iw.add_argument("--skip-source-check", action="store_true",
                    help="write even if the backup isn't the one the conversion was made from (its account "
                         "database differs); chats added on the phone since the conversion are lost on restore")
    iw.set_defaults(run=_ios_write)
    ir = i.add_parser("restore", help="put a backup `whatferry ios write` made onto its iPhone, over USB "
                                      "(replaces everything on the phone)")
    ir.add_argument("backup", type=Path, help="the backup folder `whatferry ios write` printed")
    ir.set_defaults(run=_ios_restore)

    c = sides.add_parser("convert", help="merge an Android account's chats into a copy of an iPhone account's database")
    c.add_argument("android_db", type=Path, help="decrypted msgstore.db (from `whatferry android inspect`)")
    c.add_argument("ios_db", type=Path, help="the iPhone account's ChatStorage.sqlite (from `whatferry ios inspect`)")
    c.add_argument("--media", type=Path, help="folder with the account's WhatsApp/Media contents "
                                               "(e.g. ~/whatferry-android/media/account-1001)")
    c.add_argument("--account-folder", help="data/<id> folder of a second iPhone account (omit for the main one)")
    c.set_defaults(run=_convert)

    u = sides.add_parser("ui", help="open the step-by-step wizard in your browser")
    u.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: any free one)")
    u.add_argument("--no-browser", action="store_true", help="print the link instead of opening it")
    u.set_defaults(run=_ui)
    return p


def _convert(args) -> int:
    report, run = convert.convert(args.android_db, args.ios_db, args.media, args.account_folder)
    print(f"Converted {sum(report.converted.values())} of {report.android_messages} Android messages")
    print(f"  chats: {report.chats_matched} matched, {report.chats_created} created; "
          f"group members added: {report.members_created}")
    print(f"  media: {report.media_rows} items, {report.media_files_copied} files placed, "
          f"{report.media_files_missing} missing" + ("" if args.media else " (no --media given)"))
    if report.skipped:
        print(f"  not converted (other kinds): {sum(report.skipped.values())}")
    for label, n in report.not_converted_yet.items():
        print(f"  not converted yet: {n} {label}")
    problems = {k: v for k, v in report.checks.items() if isinstance(v, int) and v and k not in ("messages", "chats")}
    print(f"  checks: integrity {report.checks['integrity']}, " + (f"problems {problems}" if problems else "no problems"))
    _print_run(run)
    return 1 if problems or report.checks["integrity"] != "ok" else 0


def _ui(args) -> int:
    from whatferry.ui.server import serve

    serve(port=args.port, open_browser=not args.no_browser)
    return 0


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


ADB_HELP = (
    "adb isn't installed. Get Google's platform-tools: "
    "https://developer.android.com/tools/releases/platform-tools "
    "(or: brew install --cask android-platform-tools · winget install Google.PlatformTools · "
    "sudo apt install adb). Or set WHATFERRY_ADB to its path.")


def _adb_tool():
    tool = adb.find_adb()
    if tool is None:
        raise adb.AdbError(ADB_HELP)
    return tool


def _android_phone(args) -> int:
    tool = _adb_tool()
    phones = adb.devices(tool)
    if not phones:
        print("No phone connected. Turn on USB debugging (see the README), plug the phone in, unlock it, "
              "and tap Allow.")
        return 0
    for phone in phones:
        print(f"{phone.model or 'Android phone'} ({phone.serial}): {'ready' if phone.ready else phone.advice}")
        if not phone.ready:
            continue
        backups = adb.phone_backups(tool, phone.serial)
        if not backups:
            print("  No WhatsApp backup on this phone yet: make one in WhatsApp → Settings → Chats → Chat backup.")
        for b in backups:
            account = f", account {b.account}" if b.account else ""
            print(f"  {'✓' if b.usable else '✗'} {b.name}  {_size(b.size)}  {b.modified}  ({b.app}{account})")
            print(f"      {b.path}")
            if b.note:
                print(f"      {b.note}")
    return 0


def _android_pull(args) -> int:
    tool = _adb_tool()
    ready = [p for p in adb.devices(tool) if p.ready and (args.serial in (None, p.serial))]
    if not ready:
        raise adb.AdbError("no ready phone: run `whatferry android phone` to see why")
    if len(ready) > 1 and not args.serial:
        raise adb.AdbError("more than one phone: choose one with --serial")
    serial = ready[0].serial
    if args.path:
        paths = [args.path]
    else:
        # One full backup per app and account: the undated msgstore file.
        paths = [b.path for b in adb.phone_backups(tool, serial) if b.usable and b.name.startswith("msgstore.")]
        if not paths:
            raise adb.AdbError("no usable backup on the phone: run `whatferry android phone` for details")
    for path in paths:
        target = adb.pull(tool, serial, path, args.to)
        print(f"Copied {path}\n    to {target}")
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
        print(how_to_back_up())
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
    for account in report.accounts:
        country = f" ({account.country})" if account.country else ""
        main = ", owns the main chat database" if account.main else ""
        print(f"  WhatsApp account id …{account.id_ends}: number ending {account.number_ends or '?'}{country}{main}")
    for folder in report.account_folders:
        has = "with" if folder.has_chat_database else "without"
        print(f"  account folder {folder.folder} {has} a chat database")
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


def _ios_write(args) -> int:
    source = _open_backup(args.backup)  # checks the passphrase before anything is copied
    target = args.to / source.folder.name if args.to else None
    report, written = backup_writer.write_conversion(source.folder, source.passphrase, args.convert_run,
                                                     args.account_folder, target,
                                                     check_source=not args.skip_source_check)
    if args.skip_source_check:
        print("Source check skipped: the conversion may not match this backup.")
    print(f"Wrote a new {'encrypted ' if report.encrypted else ''}backup: {written}")
    print(f"  replaced: {', '.join(p.split('/', 1)[1] for p in report.replaced)}")
    if report.removed:
        print(f"  removed: {', '.join(p.split('/', 1)[1] for p in report.removed)}")
    print(f"  added: {report.added_files} files ({_size(report.added_bytes)}) and {report.added_folders} folders")
    print(f"  {report.verified_files} written files read back and verified")
    print("The original backup is unchanged. Nothing has been restored to the phone.")
    return 0


def _ios_restore(args) -> int:
    folder = args.backup.expanduser()
    udid = restore.backup_udid(folder)
    backup = _open_backup(str(folder))  # checks the passphrase before the phone is touched
    phone = next((p for p in restore.iphones() if p.udid.upper() == udid.upper()), None)
    name = phone.name if phone and phone.name else udid
    print(f"This replaces everything on {name} with the backup in {folder}.")
    print("Anything that reached the phone after that backup was made will be gone.")
    if input(f"Type {name} to restore: ").strip() != name:
        print("Not restored.")
        return 1
    last = -10.0

    def progress(percent: float) -> None:
        nonlocal last
        if percent >= last + 10 or percent >= 100:
            last = percent
            print(f"  {percent:.0f}%")

    restore.restore(folder, backup.passphrase, progress)
    print(f"Restored. {name} restarts now; keep it connected until it shows the lock screen.")
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
