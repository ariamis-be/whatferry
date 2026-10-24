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
is made either way). Copy
`Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15` to the
Mac, and put the key in a file only you can read (`chmod 600`).

```sh
whatferry android inspect msgstore.db.crypt15 --key-file key.txt
```

**iPhone, before.** Finder → the iPhone → tick *Encrypt local backup* →
*Back Up Now*. The terminal needs Full Disk Access to read the backups.

```sh
whatferry ios backups
cp -R ~/Library/Application\ Support/MobileSync/Backup/<id> ~/whatferry-before
whatferry ios inspect <id>
```

Copy the backup aside: Finder updates the same folder in place.

**iPhone, after.** In WhatsApp: *Add account* with the Android number (this
signs it out on Android; the copied `.crypt15` is unaffected). Back up again
in Finder, then:

```sh
whatferry ios diff ~/whatferry-before <id>
whatferry ios inspect <id>
```

The diff names every WhatsApp file adding the account created or changed;
that is where the conversion will write.

## What stays private

- Keys and passphrases come from a file, `WHATFERRY_ANDROID_KEY` /
  `WHATFERRY_BACKUP_PASSPHRASE`, or a hidden prompt; never the command line.
- Decrypted copies go to `~/.local/share/whatferry/<time>-<kind>/`
  (`WHATFERRY_HOME` to move it), folders `0700`, files `0600`.
- The terminal shows counts, table names and paths, never message text,
  names or numbers. `report.json` and the `*.schema.sql` files beside the
  decrypted copies hold the same: shape, not content.
- Delete the run folders when done: `rm -rf ~/.local/share/whatferry`.

## Development

```sh
mise exec -- uv run pytest
```

The tests build a real `.crypt15` with wa-crypt-tools' own encryptor and an
unencrypted Finder-format backup (Manifest.db, keyed-archiver file plists,
hashed file names). Encrypted iPhone backups are read through
iphone_backup_decrypt and are not covered by a fixture yet.

wa-crypt-tools is GPL-3.0, so whatferry is too, if it is ever distributed.
