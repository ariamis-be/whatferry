# Security

whatferry handles decrypted WhatsApp histories, the Android backup's 64-digit
key and the iPhone backup's passphrase. It runs entirely on your computer and
sends nothing anywhere.

## Reporting a problem

Please report security problems privately, through **Report a vulnerability**
on the repository's Security tab (GitHub private vulnerability reporting),
not in a public issue. Include the whatferry version (`whatferry --version`),
your system, and how to reproduce it. Never include a real backup, key or
passphrase.

You can expect a first answer within a week. Fixes go into a new release,
and the advisory is published once that release is out.

## Supported versions

Only the newest release gets fixes.

## What whatferry does to stay safe

- Keys and passphrases come from a file, an environment variable or a hidden
  prompt, never the command line, and are never saved.
- Decrypted copies go to a private folder (`0700` folders, `0600` files on
  macOS and Linux) that `whatferry clean` deletes.
- The wizard listens on 127.0.0.1 only, behind a random token, checks the
  Host and Origin headers, and serves a Content-Security-Policy that allows
  only its own script.
- A backup you made is never changed: whatferry writes a new one beside it,
  and checks it by reading it back with an independent reader.
- Restoring refuses a backup from another iPhone, an untrusted computer, a
  wrong passphrase, or a phone with Find My on.

The [README](README.md#what-stays-private) has the details.
