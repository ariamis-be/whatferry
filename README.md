# whatferry

Move WhatsApp chats between Android and iPhone, in either direction, without
Move to iOS and without erasing the iPhone. On the iPhone, the Android
number's chats can go into:

- a fresh WhatsApp, when the iPhone has none yet;
- a second account, next to a WhatsApp account the iPhone already runs;
- the existing account, when it already uses the Android number, merged with
  the chats it has.

From an iPhone to an Android phone, see
[iPhone to Android](https://github.com/ariamis-be/whatferry#iphone-to-android).

So far the second-account move is the one done on a real phone (below). The
others are covered by the tests and wait for their first real transfer.

It never changes a backup you made: it writes a new one beside it. The only
thing it writes to a phone is that new backup, restored over USB when you ask
and confirm.

> **Important:** whatferry is an independent project. It is not made,
> endorsed or supported by WhatsApp, Meta, Apple or Google, and their names
> are used only to say what it works with. It reads and writes WhatsApp's
> private database formats, which can change with any WhatsApp update: it
> checks them first (see
> [Compatibility](https://github.com/ariamis-be/whatferry#compatibility)),
> but a restore replaces what is on the iPhone with the backup. Keep the backups you made until the moved chats
> look right, and use it at your own risk. The licence below comes with no
> warranty.

## How the transfer works

1. Android: WhatsApp's end-to-end encrypted backup, with the 64-digit key,
   gives a `msgstore.db.crypt15` file whatferry can decrypt without root.
2. iPhone: set up WhatsApp with the Android number, either as its only
   account or added as a second one. WhatsApp itself creates that account's
   database, folders and keys.
3. whatferry converts the Android messages into WhatsApp for iOS's Core Data
   database and fills only that account's database, inside an encrypted
   Finder backup of the iPhone.
4. That edited backup is restored to the same iPhone. Any other account's
   files are restored as the backup had them, never edited.

All four steps are built. The second-account move has carried a real account
(its full history, media included) onto a real iPhone.

## Setup

Runs on macOS, Windows and Linux, with Python 3.14. The easiest way is
[uv](https://docs.astral.sh/uv/), which fetches that Python itself:

```sh
uvx whatferry ui          # run the wizard without installing anything
uv tool install whatferry # or install the `whatferry` command
```

`pipx install whatferry` works too. On Linux, talking to an iPhone needs the
`usbmuxd` package; on macOS and Windows, Finder or the Apple Devices app
already brings it.

## The wizard

```sh
whatferry ui
```

opens a step-by-step page in your browser that does everything below:
finds the Android backup in Downloads (or takes it from a file picker),
decrypts it with the key you type, backs up the iPhone over the cable (or
lists the backups Finder made), checks the first one and keeps its file list, walks through adding
the second account, then compares the second backup with the first and points
at the new account's chat database. Then it converts the chats into the
iPhone account picked (suggesting the one on the Android number, and the
media folder that has the Android history's files), shows a preview of the
result (every chat the account will have, marked new, joined or iPhone-only,
with names from the iPhone's WhatsApp contacts, and each chat's newest
messages with the Android ones outlined), writes the new backup,
and restores it onto the iPhone. The last step is a summary to copy and send
on: counts, versions and file locations, with phone numbers masked.

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

The page is in 21 languages: English, Arabic, Bengali, Chinese (Simplified
and Traditional), Dutch, French, German, Hebrew, Hindi, Indonesian, Italian,
Malay, Persian, Polish, Portuguese (Brazil), Romanian, Spanish, Turkish,
Ukrainian and Urdu, with Arabic, Hebrew, Persian and Urdu laid out right to
left. It starts in the browser's language, and the header switches it. It
has a light, dark or system theme, system by default. Both choices are kept in `settings.json` in whatferry's folder,
not in the browser, which keeps them per port, and the port changes on every
start. Messages from the server,
and the summary to send on, stay in English.

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
(ZDOCID), media download keys and the ZMETADATA thumbnail blob. Search in
WhatsApp on the iPhone may not find the moved messages until it rebuilds its
own index: that index uses a tokenizer only the app has, so whatferry can't
add to it.

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

## Restoring it onto the iPhone

```sh
whatferry ios restore <the backup folder `ios write` printed>
```

puts the new backup onto the iPhone it came from, over USB, as Finder's
Restore Backup does: system files and settings too, then a restart. The
iPhone goes back to the moment of its backup, plus the converted chats;
anything that reached it later is gone. It asks for the passphrase and for
the iPhone's name to be typed before it starts.

It talks to the phone with [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
through usbmuxd (Apple's on macOS and Windows, which comes with Finder or the
Apple Devices app; the `usbmuxd` package on Linux), and only to an iPhone
this computer is already paired with. It refuses, before touching the phone,
when the backup's device ID isn't the connected iPhone's, when the computer
isn't trusted, when the passphrase is wrong, or when Find My is on (iOS
would refuse it anyway; `com.apple.fmip`/`IsAssociated` says so beforehand).
With Stolen Device Protection on, iOS only lets Find My be turned off after
it (Settings → Face ID & Passcode), which away from a familiar location
means an hour's Security Delay.

## iPhone to Android

The same steps the other way round; the wizard's Start page picks the
direction.

1. **iPhone:** an encrypted Finder backup, checked as before. Its chats are
   read, and its photos, videos and voice notes are taken out of it.
2. **Android:** WhatsApp signed in to the number being moved, then its
   end-to-end encrypted backup (`msgstore.db.crypt15`, with the 64-digit key),
   checked as before. That backup is the template: WhatsApp's own database for
   the account, of the version on the phone.
3. **Convert:** the iPhone history is merged into a copy of it, rows filled
   the way WhatsApp for Android writes them (measured on a real
   database), media laid out under `Media/WhatsApp Images/Sent/…` and the rest.
   New files say `WF` where WhatsApp says `WA` (`IMG-20261025-WF0001.jpg`), so
   they can't share a name with a file WhatsApp made; WhatsApp finds media by
   the database's path, not the name. The same preview shows the result.
4. **Write:** the merged database is encrypted like WhatsApp's backup, with
   the original's header and a fresh IV (never the original's: that would
   reuse an AES-GCM nonce under the same key), then decrypted again and
   compared. The same-source guard applies.
5. **Copy:** with WhatsApp's storage cleared on the phone, the backup and
   media go into WhatsApp's folder over adb. The phone's own backup is kept
   under a new name, and nothing is copied at all if any media name is
   already taken there. Then WhatsApp is opened, the number verified, and the
   backup restored with the key, as WhatsApp's own restore.

```sh
whatferry android convert <ios run>/…/ChatStorage.sqlite <android run>/msgstore.db \
  --backup <iphone backup> --account-folder data/<id>
whatferry android write ~/whatferry-android/msgstore.db.crypt15 <convert run folder>
whatferry android push <the WhatsApp folder `android write` printed>
```

Only the main WhatsApp folder and `accounts/<n>/` folders the phone lists
are written to. Not yet tried end to end on a real Android phone.

## Compatibility

Before converting, both databases are checked for every table and column
the conversion reads or writes; anything missing stops it with the list,
instead of a failure half-way.

Then the whole layout is compared with the snapshots whatferry was measured
on, kept in [`src/whatferry/schemas/`](https://github.com/ariamis-be/whatferry/tree/master/src/whatferry/schemas): tables,
columns with their types, NOT NULL and defaults, indexes, triggers, views,
the iPhone's Core Data entities and the database version, and nothing the
database stores. Today that is WhatsApp for iOS database model 2.12.14 and
WhatsApp for Android 2.26.41 (database version 1). Matching goes by layout,
not app version: WhatsApp ships every week, and most releases leave the
database alone. Each difference from the closest snapshot is sorted:

- **harmless**: a table or column the conversion doesn't use, a new table.
  It converts as usual.
- **review**: a table the conversion writes gained a column, an index or a
  new default, or the database version moved. It converts, with a note on
  the Convert page to look through the preview first.
- **stop**: a column or table the conversion uses is gone, or a table it
  writes gained a NOT NULL column with no default, a unique index or a
  trigger, or an entity it writes was removed. It refuses, naming the change.

A column on a table the conversion writes that no snapshot has is filled
with the value WhatsApp's own rows in that database agree on (at least 90%
of 10 or more rows); if they don't agree, it keeps its default. The report
lists every column filled this way. That covers the usual "new flag column"
release without a code change.

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

**iPhone, before.** Make an encrypted backup. Connect the iPhone with a
cable, unlock it, and on any system:

```sh
whatferry ios backup
```

It finds the iPhone (asking it to trust this computer if it doesn't yet),
and makes the same backup Finder makes, through the same service on the
phone, into `<whatferry's folder>/backups/<id>`. When the phone doesn't
encrypt its backups yet, it asks for a passphrase twice and turns encryption
on: that is the phone's own setting, the one Finder's *Encrypt local backup*
box shows. When it already encrypts, the passphrase is asked once and checked
by opening the backup, before an update and after the backup. Later runs
update the same folder, as Finder does; `--full` starts over. The wizard has
the same as a *Back up now* button. No Finder, Apple Devices app or Full Disk
Access is needed.

`whatferry ios backup --whatsapp-only` keeps only WhatsApp's two containers.
It takes seconds instead of an hour, which suits `ios diff`, and lands in
`<id>-whatsapp`, replaced each time. It holds nothing else of the phone, so
`ios restore` refuses it.

Or by hand:

| System | How | Where it lands |
|---|---|---|
| macOS | Finder → the iPhone → tick *Encrypt local backup* → *Back Up Now*. The terminal needs Full Disk Access to read it. | `~/Library/Application Support/MobileSync/Backup/<id>` |
| Windows | Apple Devices app (or iTunes) → the iPhone → tick *Encrypt local backup* → *Back Up Now* | `%USERPROFILE%\Apple\MobileSync\Backup\<id>`, or `%APPDATA%\Apple Computer\MobileSync\Backup\<id>` for iTunes from apple.com |
| Linux | libimobiledevice: `idevicebackup2 encryption on` once, then `idevicebackup2 backup --full <folder>` | `<folder>/<id>`; set `WHATFERRY_BACKUP_ROOT=<folder>` |

whatferry's own folder is listed first, then the system's. When both hold a
backup of the same phone, `ios backups` shows full paths and the bare `<id>`
picks whatferry's. `WHATFERRY_BACKUP_ROOT` works on every system and replaces
them all (several folders: join them with `:`, or `;` on Windows).

Writing a backup copies it first. macOS clones it on APFS, Linux shares
blocks where the file system can (`cp --reflink=auto`), and elsewhere it is a
full copy: whatferry checks there is room before starting, and on Windows
says how much it needs.

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
- The one exception is the wizard's preview of a conversion, which shows chat
  names, messages and converted photos so you can check the result before
  writing it. It is read from the merged copy on request, sent only to the
  local page (with `Cache-Control: no-store`), and never saved in
  `state.json`, a report or the summary.
- Delete the run folders when done: `whatferry clean` lists them, with the
  space each gives back, and asks before deleting (`--dry-run` only lists,
  `--yes` doesn't ask). It also deletes the wizard's progress, the Manifest
  snapshots it compares and the private `tmp/` folder; it keeps
  `settings.json`, and the iPhone backups `whatferry ios backup` made unless
  you add `--backups`. Finder's backups and the Android copies in
  `~/whatferry-android` are never touched. Close the wizard first.

## Contributing

To help, see [`CONTRIBUTING.md`](https://github.com/ariamis-be/whatferry/blob/master/CONTRIBUTING.md); to report a security
problem, see [`SECURITY.md`](https://github.com/ariamis-be/whatferry/blob/master/SECURITY.md). Changes are listed in
[`CHANGELOG.md`](https://github.com/ariamis-be/whatferry/blob/master/CHANGELOG.md).

## Licence

[GPL-3.0-or-later](https://github.com/ariamis-be/whatferry/blob/master/LICENSE). whatferry imports pymobiledevice3 and
wa-crypt-tools, which are both GPL-3.0-or-later, so it is too.

WhatsApp is a trademark of WhatsApp LLC; iPhone, iOS and Finder are
trademarks of Apple Inc.; Android is a trademark of Google LLC.
