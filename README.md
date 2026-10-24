# whatferry

Move WhatsApp chats from an Android phone to an iPhone that is already set
up, without Move to iOS and without erasing the iPhone. It is built for an
iPhone that already runs one WhatsApp account and will add the Android one as
its second.

**This version only reads.** It decrypts and describes backups so the
conversion can be designed against real data; it never writes to a phone or
to a backup.

## How the transfer will work

1. Android: WhatsApp's end-to-end encrypted backup, with the 64-digit key,
   gives a `msgstore.db.crypt15` file whatferry can decrypt without root.
2. iPhone: add the Android number as a second account in WhatsApp, so
   WhatsApp itself creates that account's empty database, folders and keys.
3. whatferry converts the Android messages into WhatsApp for iOS's Core Data
   database and fills only that new account's database, inside an encrypted
   Finder backup of the iPhone.
4. That edited backup is restored to the same iPhone. The other account's
   files are never written.

Steps 3 and 4 are not built yet. Discovery comes first: finding where
WhatsApp keeps each account, and what both databases look like today.

## Setup

Runs on macOS, Windows and Linux with [mise](https://mise.jdx.dev), which
installs the pinned Python and uv:

```sh
mise install
mise exec -- uv sync
mise exec -- uv run whatferry --help
```

The commands below write `whatferry` for `mise exec -- uv run whatferry`.

## Discovery, step by step

**Android.** In WhatsApp: Settings → Chats → Chat backup → End-to-end
encrypted backup → turn on → *Use 64-digit encryption key instead*, and note
the key. Then *Back up* (Google Drive may be set to *Never*; the local file
is made either way). Get
`Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15` onto the
computer: share it from the phone's file manager (LocalSend, Google Drive),
copy it over USB in file-transfer mode (Windows and Linux browse the phone
directly; macOS needs OpenMTP), or `adb pull` it. Put the key in a file only
you can read.

```sh
whatferry android inspect msgstore.db.crypt15 --key-file key.txt
```

**iPhone, before.** Make an encrypted backup:

| System | How | Where it lands |
|---|---|---|
| macOS | Finder → the iPhone → tick *Encrypt local backup* → *Back Up Now*. The terminal needs Full Disk Access to read it. | `~/Library/Application Support/MobileSync/Backup/<id>` |
| Windows | Apple Devices app (or iTunes) → the iPhone → tick *Encrypt local backup* → *Back Up Now* | `%USERPROFILE%\Apple\MobileSync\Backup\<id>`, or `%APPDATA%\Apple Computer\MobileSync\Backup\<id>` for iTunes from apple.com |
| Linux | libimobiledevice: `idevicebackup2 encryption on` once, then `idevicebackup2 backup --full <folder>` | `<folder>/<id>`; set `WHATFERRY_BACKUP_ROOT=<folder>` |

`WHATFERRY_BACKUP_ROOT` works on every system and replaces the defaults
(several folders: join them with `:`, or `;` on Windows).

```sh
whatferry ios backups
whatferry ios inspect <id>
```

Then copy the `<id>` folder somewhere else, for example `~/whatferry-before`:
the next backup updates the same folder in place.

**iPhone, after.** In WhatsApp: *Add account* with the Android number (this
signs it out on Android; the copied `.crypt15` is unaffected). Back up again
the same way, then:

```sh
whatferry ios diff ~/whatferry-before <id>
whatferry ios inspect <id>
```

The diff names every WhatsApp file adding the account created or changed;
that is where the conversion will write.

## What stays private

- Keys and passphrases come from a file, `WHATFERRY_ANDROID_KEY` /
  `WHATFERRY_BACKUP_PASSPHRASE`, or a hidden prompt; never the command line.
- Decrypted copies go to `<time>-<kind>/` folders under
  `~/.local/share/whatferry` (macOS, Linux; `$XDG_DATA_HOME/whatferry` when
  set) or `%LOCALAPPDATA%\whatferry` (Windows); `WHATFERRY_HOME` moves it.
  On macOS and Linux folders are `0700` and files `0600`. Windows has no such
  modes: there the user profile's own access list keeps the default location
  private, so set `WHATFERRY_HOME` only to a folder inside your profile.
- The terminal shows counts, table names and paths, never message text,
  names or numbers. `report.json` and the `*.schema.sql` files beside the
  decrypted copies hold the same: shape, not content.
- Delete the run folders when done.

## Development

```sh
mise exec -- uv run pytest
```

The tests build a real `.crypt15` with wa-crypt-tools' own encryptor and an
unencrypted Finder-format backup (Manifest.db, keyed-archiver file plists,
hashed file names). Encrypted iPhone backups are read through
iphone_backup_decrypt and are not covered by a fixture yet.
`tests/test_platforms.py` covers what differs by system: backup and data
folders, file names Windows refuses, `file:` URIs for paths holding `#`, `?`
or `%`, and byte-exact writes. CI runs the suite on macOS, Windows and Linux.

wa-crypt-tools is GPL-3.0, so whatferry is too, if it is ever distributed.
