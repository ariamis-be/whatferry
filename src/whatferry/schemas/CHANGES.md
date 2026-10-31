# WhatsApp database layouts

One JSON file per layout whatferry has seen, in `ios/` and `android/`, named
by its fingerprint (`whatferry schema capture` writes them). Each file holds
the layout only (tables, columns, indexes, triggers, views, entities and
version) and lists the app versions it was seen with. None of them holds
anything a database stores, so they are safe to commit.

## After a WhatsApp update

Do this when WhatsApp updates on either phone, or once a month, whichever
comes first. It takes about ten minutes, most of it waiting for the backups.

1. **Android**: in WhatsApp, Settings → Chats → Chat backup → *Back up*.
   Then:

   ```sh
   whatferry android pull
   whatferry android inspect <the pulled msgstore.db.crypt15> --key-file <key file>
   ```

   `inspect` prints the WhatsApp version that made the backup and the run
   folder holding the decrypted `msgstore.db`.
2. **iPhone**: make an encrypted Finder backup, then
   `whatferry ios inspect <backup>`. It prints the run folder holding
   each account's `ChatStorage.sqlite`. The app version is in WhatsApp →
   Settings → Help, or on its App Store page.
3. **Check**: `whatferry schema check <db>` for each database.
   - *Nothing that matters changed*, and the layout is the same: run
     `whatferry schema capture <db> --app-version <version>` to record the
     version as seen. That's all.
   - A new layout with only **harmless** or **review** items: capture it,
     and add a line below saying what changed (`schema check --all` lists
     everything). Next time you convert, look through the preview.
   - Any **stop** item: whatferry refuses this database until it is handled.
     Capture it, note it below, and change the converter (`compat.py` lists
     the columns each direction uses; `convert.py` and `to_android.py`
     write the rows).
4. Commit the new or updated snapshot files with this log.

As an early warning, the open-source WhatsApp exporters run into the same
changes, often first: watch the releases and issues of
[WhatsApp-Chat-Exporter](https://github.com/KnugiHK/WhatsApp-Chat-Exporter).

## Log

Newest first. One entry per new layout: date, platform, app version, what
changed and what it meant.

- **2026-10-25**: iOS, database model 2.12.14 (`ios/3ca296bd35e652d3.json`),
  from both accounts on the iPhone. Android, WhatsApp 2.26.41.77, database
  version 1 (`android/778707c93e75c22c.json`), from the Pixel's backups.
  These are the layouts the converters were measured on and the first
  real transfer used.
