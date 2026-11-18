# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-19

The first public release.

### Added

- Android to iPhone: decrypt the Android `.crypt15` backup with its 64-digit
  key, convert the chats and media into WhatsApp for iOS's database, write
  them into a new copy of an encrypted iPhone backup, and restore it. The
  chats can go into a fresh WhatsApp, a second account, or the existing
  account on the same number, merged with the chats it has. Several Android
  accounts can be moved in turn.
- iPhone to Android: the same steps the other way, through WhatsApp's own
  restore from a `.crypt15` backup, copied onto the phone over adb.
- The wizard (`whatferry ui`): every step in the browser, in 21 languages,
  four of them right to left, with a light, dark or system theme. It
  suggests where the chats should go from the numbers the backups are
  signed in as, and shows a preview of the result before anything is
  written.
- `whatferry ios backup`: encrypted iPhone backups on macOS, Windows and
  Linux without Finder; `--whatsapp-only` for a quick one to compare.
- `whatferry android phone` and `whatferry android pull`: find and copy the
  Android backups over USB debugging.
- Compatibility checks against committed snapshots of WhatsApp's database
  layouts, on both phones, before anything is converted, and
  `whatferry schema check` and `capture` for after a WhatsApp update.
- `whatferry clean`: deletes the decrypted copies and progress whatferry left.
- `whatferry --version`.

### Safety

- A backup you made is never changed: the result is written into a new copy
  and read back with an independent reader.
- A conversion is only written into the backup it was made from
  (`--skip-source-check` overrides it, and says so).
- Restoring refuses a backup from another iPhone, an untrusted computer, a
  wrong passphrase, or a phone with Find My on.

### Not converted yet

Quoted replies, reactions, polls, calls and system notices are counted in
the report but not carried across.

### Known limits

- Moving Android to a second iPhone account has been done on a real phone.
  The other moves, iPhone to Android included, are covered by the tests and
  wait for their first real transfer.
- WhatsApp's search on the iPhone may not find moved messages until it
  rebuilds its own index.
