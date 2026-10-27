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

## The wizard

```sh
whatferry ui
```

opens a step-by-step page in your browser that does everything below:
finds the Android backup in Downloads (or takes it from a file picker),
decrypts it with the key you type, lists the iPhone backups on this
computer, checks the first one and keeps its file list, walks through adding
the second account, then compares the second backup with the first and points
at the new account's chat database. The last step is a summary to copy and
send on: counts, versions and file locations, with phone numbers masked.

Progress is saved, so the page can be closed while a backup runs; keys and
passphrases are never saved. The page is served on 127.0.0.1 only, behind a
random token in the link it opens, with the Host and Origin headers checked
and a Content-Security-Policy that allows only its own script.
`whatferry ui --no-browser` prints the link instead of opening it.

After the first iPhone backup, the wizard asks where the Android chats should
go, and suggests an answer:

- **Set up WhatsApp** with the Android number, when the iPhone has no
  WhatsApp yet;
- **a second account**, when the iPhone's WhatsApp uses another number (the
  usual case);
- **the existing account**, when an account there already uses the Android
  number; the second backup is then skipped, and the chats will be merged
  into that account's own.

It reads the number the iPhone's WhatsApp is signed in as
(`LastOwnJabberID` in the app group's shared preferences, read with a
lenient parser because the file holds a date Python can't) and compares its
last digits with the Android backup's two, all the Android header keeps.
Only the last four digits are stored or shown. Further accounts only show as
`data/<id>/` folders, whose number can't be read, so the wizard says there
*may* be a second account. Two sources that looked right were checked
against a real phone and dropped: the keyboard's `ID_<lid>@lid` entries and
ChatStorage's profile-name row both belong to contacts.

The page is in English and Simplified Chinese (it starts in the browser's
language; the header switches it), with light, dark or system theme (system
by default). Both choices are kept in the browser. Messages from the server,
and the summary to send on, stay in English.

The page is React with shadcn/ui, built from `web/` into
`src/whatferry/ui/static/` and committed, so running whatferry needs only
Python. To change it, see [`web/README.md`](web/README.md).

## Converting

```sh
whatferry convert <android run>/msgstore.db \
  <ios run>/files/AppDomainGroup-group.net.whatsapp.WhatsApp.shared/data/<id>/ChatStorage.sqlite \
  --media ~/whatferry-android/media/account-1001 --account-folder data/<id>
```

merges the decrypted Android history into a **copy** of the iPhone account's
ChatStorage.sqlite, in a new private run folder, with the media laid out
where the iPhone keeps it (`data/<id>/Message/Media/<chat>/<x>/<y>/<uuid>.<ext>`;
hard links, so no extra space). Leave out `--account-folder` for the main
account. Nothing is written to a phone or a backup.

Rows are filled the way WhatsApp itself writes them, measured on a real
iPhone: direction in ZFROMJID/ZTOJID, group senders as ZWAGROUPMEMBER rows,
ZSORT by date within a chat, image size in ZLATITUDE/ZLONGITUDE, MIME type
and SHA-256 in the media row's vCard columns. Chats are matched by JID, an
Android privacy ID (`@lid`) by the phone number it maps to; history lands
before anything the iPhone account already has.

Converted: text, images, videos, audio and voice notes, documents, GIFs,
stickers, locations, contact cards, deleted-message placeholders. Not yet:
quoted replies, reactions, polls, calls, system notices (all counted in the
report). Left empty, pending a test on a phone: the search index ID
(ZDOCID), media download keys and the ZMETADATA thumbnail blob.

## Writing the result into a backup

```sh
whatferry ios write <backup> <convert run folder> --account-folder data/<id>
```

copies the backup the conversion came from (an APFS clone on macOS: instant,
no extra space) and writes into the copy: the merged ChatStorage.sqlite
replaces the account's, its old `-wal`/`-shm` are removed (they would be
replayed over it), and every converted media file is added with its folder
entries. Encrypted backups are written as iOS writes them: each file
AES-256-CBC under a fresh key, wrapped (RFC 3394) with its protection
class's keybag key; Manifest.db re-encrypted under the same manifest key.
New entries are cloned from entries iOS wrote in the same backup. Every
written file is then read back with an independent reader
(iphone_backup_decrypt) and compared. The original backup is never changed.

It only writes into the backup the conversion was made from. `whatferry
convert` records the SHA-256 of the iPhone database it merged into and the
account folder; before writing anything, `ios write` extracts that account's
database from the backup it was given (with its `-wal` folded in) and refuses
if the fingerprint or the account differs. Restoring rolls the whole phone
back to the backup, so a newer backup means converting again from it, not
writing an old conversion into it. `--skip-source-check` writes anyway (and
says so in the output and in write-report.json); whatever the account gained
on the phone after the conversion's backup is then lost on restore.

The passphrase comes from `WHATFERRY_BACKUP_PASSPHRASE` or a hidden prompt.
The new backup goes to a private run folder unless `--to` says otherwise.

Restoring it to the iPhone is the next step, not built yet.

## The same steps on the command line

**Android.** In WhatsApp: Settings → Chats → Chat backup → End-to-end
encrypted backup → turn on → *Use 64-digit encryption key instead*, and note
the key. Then *Back up* (Google Drive may be set to *Never*; the local file
is made either way). With more than one WhatsApp account on the phone, each
account has its own backup and key: switch to the account first.

The backup is `msgstore.db.crypt15` (the undated one) in:

| Setup | Folder on the phone |
|---|---|
| One account | `Android/media/com.whatsapp/WhatsApp/Databases` |
| Several accounts | `Android/media/com.whatsapp/WhatsApp/accounts/<number>/Databases` |
| WhatsApp Business | `Android/media/com.whatsapp.w4b/WhatsApp Business/Databases` (or `…/accounts/<number>/Databases`) |
| Android 10 or older | `WhatsApp/Databases` |

`.crypt14`, dated and `increment` files can't be used: their key only exists
on a rooted phone, or they are partial.

Get it onto the computer any way you like:

- **Share from the phone**: the Files app → that folder → long-press → Share,
  to LocalSend, Quick Share (Windows), Google Drive, or email/a message to
  yourself.
- **USB file transfer**: plug in, choose *File transfer* on the phone;
  Windows and Linux open the phone directly, macOS needs OpenMTP.
- **USB debugging (adb)**: whatferry copies it itself.
  1. Settings → About phone → tap *Build number* seven times (Samsung:
     About phone → Software information → Build number).
  2. Settings → System → Developer options → *USB debugging* on.
  3. Plug in, unlock, tap *Allow* on "Allow USB debugging?".
  4. `whatferry android phone` lists the phone's backups;
     `whatferry android pull` copies every usable one (one per account) to
     `~/whatferry-android/`. The wizard has the same as a button.

  whatferry finds adb on `PATH`, in Android Studio's SDK, `ANDROID_HOME`, or
  mise's android-sdk; `WHATFERRY_ADB` points it elsewhere. No adb yet:
  `brew install --cask android-platform-tools`,
  `winget install Google.PlatformTools`, `sudo apt install adb`, or Google's
  platform-tools download. Turn USB debugging off again afterwards.

Put the key in a file only you can read, then:

```sh
whatferry android inspect ~/whatferry-android/whatsapp-account-1001-msgstore.db.crypt15 --key-file key.txt
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
