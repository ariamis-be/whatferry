# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - unreleased

The first public release.

### Added

- Android to iPhone: decrypt the Android `.crypt15` backup with its 64-digit
  key, convert the chats and media into WhatsApp for iOS's database, write
  them into a new copy of an encrypted iPhone backup, and restore it. The
  chats can go into a fresh WhatsApp, a second account, or the existing
  account on the same number.
- iPhone to Android: the same steps the other way, through WhatsApp's own
  restore from a `.crypt15` backup, copied onto the phone over adb.
- `whatferry ios backup`: encrypted iPhone backups on macOS, Windows and
  Linux without Finder.
- The wizard (`whatferry ui`): every step in the browser, in 21 languages,
  four of them right to left.
- Compatibility checks against committed snapshots of WhatsApp's database
  layouts, on both phones, before anything is converted.
- `whatferry clean`: deletes the decrypted copies and progress whatferry left.
- `whatferry --version`.

### Not converted yet

Quoted replies, reactions, polls, calls and system notices are counted in
the report but not carried across.
