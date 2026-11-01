# Plan: `whatferry ios backup` and a monthly round-trip harness

Two parts, because they are separable: the backup command
is useful to every whatferry user on its own; the harness builds on it.

## Part A — the backup command

**Goal.** One command that makes the encrypted iPhone backup on macOS, Windows
and Linux, so Finder / Apple Devices / `idevicebackup2` disappear from the
instructions, Full Disk Access is no longer needed on macOS, and the harness
has a backup step it can call.

Finder, the Apple Devices app, `idevicebackup2` and pymobiledevice3 are all
clients of the same `com.apple.mobilebackup2` service on the phone. Confirmed
on pymobiledevice3 11.44.0 (the pinned version):

- `backup2 backup --full <folder>` writes `<folder>/<udid>/` in Finder's
  layout (`Manifest.db`, `Manifest.plist`, `Info.plist`, `Status.plist`, files
  under two-hex-character folders), the format `ios_backup.py` reads and
  `restore.py` restores. Without `--full` it is incremental into an existing
  folder, like Finder updating the same `<id>` in place.
- `backup2 encryption on <password>` sets the *device's* `WillEncrypt` flag —
  the very flag Finder's "Encrypt local backup" checkbox toggles. API:
  `Mobilebackup2Service.get_will_encrypt()` and `change_password(new=…)` /
  `change_password(old=…)`.
- `Mobilebackup2Service.backup(full, backup_directory, progress_callback,
  filter_callback, password, patch_manifest)`.

**Where.** Move the phone-side code out of `restore.py` into a new module
`iphone.py`: `iphones()`, `Iphone`, `backup()`, `encryption()`, `restore()`.
`restore.py`'s guards stay as they are; it imports discovery. Same split as
today: the functions that actually talk to pymobiledevice3 (`_list`,
`_backup`, `_restore`) kept apart so tests stand in for them.

**`whatferry ios backup [--full] [--udid …]`**

1. Find the paired iPhone as `restore()` does. Unlike restore, allow
   `autopair=True` here: on Linux nothing else ever pairs, and the worst it
   does is show "Trust This Computer?" on the phone. Error texts as in restore
   ("unlock it", "tap Trust").
2. `get_will_encrypt()`. Off → ask a passphrase twice, `change_password(new=…)`,
   say that this is now the phone's setting (Finder will show the box
   ticked). On → ask the passphrase once; it can't be checked against the
   phone, so it is checked after the backup by opening `Manifest.db` as
   `ios inspect` does, and a wrong one is reported without discarding the
   backup.
3. `backup(full=…, backup_directory=home()/"backups", progress_callback=…)`
   → `<home>/backups/<udid>/`, Finder's layout. Default incremental like
   Finder; `--full` to start over. Progress on the terminal, and through
   `Jobs.start(progress=True)` in the wizard.
4. Add `<home>/backups` to `backup_roots()` so `ios backups`, `ios inspect`,
   `ios diff`, `ios write` and the wizard see it without
   `WHATFERRY_BACKUP_ROOT`. Print the `<id>` and the next command, as the
   other commands do.

**Wizard.** A *Back up now* button on the iPhone step with a progress bar,
used for both the "before" and the "after adding the account" backups; the
Finder / Apple Devices text stays as the alternative.

**Smaller things in the same change.**

- `clone_folder`: `cp --reflink=auto` on Linux before falling back to
  `copytree`; on Windows, say how much space the copy needs before starting.
- `ios diff` and the harness want a cheap WhatsApp-only backup:
  `filter_callback` + `patch_manifest=True` on the two WhatsApp domains
  (`AppDomain-net.whatsapp.WhatsApp`,
  `AppDomainGroup-group.net.whatsapp.WhatsApp.shared`). Forces a full backup
  and needs the passphrase, but takes seconds instead of an hour.
  `whatferry ios backup --whatsapp-only`; never a restore source (the
  same-source guard already refuses it: different `Manifest.db`).
- Tests: a fake `_backup` that writes the unencrypted Finder-format folder the
  fixtures already build; `test_platforms.py` gets the new root. README: the
  OS table becomes one command plus "or by hand".

Estimate: a day, including README and wizard.

## Part B — the harness

**Goal.** Once a month, with nobody present: Android → iPhone, verify,
iPhone → Android, verify, report. Never touch any phone that isn't the test
kit.

### B1. Fixed test kit (one-time, by hand)

| | |
|---|---|
| Test iPhone | no passcode, Find My off, Stolen Device Protection off, Auto-Lock Never, Apple ID signed in (WhatsApp re-downloads after a restore), WhatsApp with account **A** as the main account; iOS auto-update off |
| Pixel | USB debugging, *Stay awake*, SIM **B** inside permanently, WhatsApp auto-update **on** (catching updates is the point) |
| Numbers | A stays on the iPhone forever; B is ferried. Two prepaid SIMs, real carriers (VoIP numbers are often refused); a calendar reminder for whatever keeps them alive |
| Computer | always-on Mac or Linux box, powered hub, both phones never unplugged; `launchd` / systemd timer monthly |
| Secrets | one 0600 file: backup passphrase, B's 64-digit key, the allow-listed UDID and adb serial. The harness refuses to start if a connected phone isn't on the list |

### B2. Shape

A separate package in the repo (`harness/`, its own dependency group — not
shipped with whatferry), importing whatferry as a library:

- `devices.py` — `Android` (adb + Maestro flows) and `Iphone` (whatferry's
  `iphone.py`, plus pymobiledevice3 screenshot / app launch).
- `flows/` — Maestro YAML for each WhatsApp screen sequence, one file per
  screen family so an update breaks one file, not the run.
- `otp.py` — reads WhatsApp's code from the Pixel's inbox
  (`adb shell content query --uri content://sms/inbox`), for typing on the
  iPhone. B's SIM lives in the Pixel whichever phone B is registered on.
- `oracle.py` — chat fingerprint (per chat: message count, text hashes, media
  hashes) through whatferry's own readers, plus the allow-list of known losses
  (replies, reactions, polls, calls) so a passing run diffs to zero.
- `scenarios.py` — `a2i`, `i2a`, `roundtrip`; every step idempotent, state in
  `runs/<date>/state.json`, `harness resume` continues from the failed step.
- `report.py` — one folder per run with logs, every screenshot, the compat
  reports, the fingerprint diff; one notification (ntfy or mail) on pass /
  pause / fail with a one-line summary.

### B3. The steps and what drives each

Android → iPhone:

| Step | Driven by | Human? |
|---|---|---|
| Preflight: phones on the allow-list, WhatsApp versions logged, `schema check` both sides | adb, pymobiledevice3, whatferry | no |
| B registered on the Pixel (if not: register — WhatsApp reads the SMS itself) | Maestro | no |
| WhatsApp *Back up* with the 64-digit key; `android pull` | Maestro, whatferry | no |
| iPhone: B removed from WhatsApp (fresh empty DB on re-add) | iOS taps | see B4 |
| `ios backup` ("before") | whatferry | no |
| iPhone: *Add account* B, type the code from `otp.py` | iOS taps | see B4 |
| `ios backup` ("after"), `ios diff`, `convert`, `ios write` | whatferry | no |
| `ios restore` | whatferry | no |
| Wait for reboot: poll `iphones()` until paired again; post-restore panes | pymobiledevice3; iOS taps | see B4 |
| Open WhatsApp, switch to B, let it migrate; screenshot | iOS taps / `dvt launch` | see B4 |
| `ios backup --whatsapp-only`, fingerprint against the seed, report | whatferry, oracle | no |

iPhone → Android:

| Step | Driven by | Human? |
|---|---|---|
| `ios backup` | whatferry | no |
| Template: `pm clear com.whatsapp`, register B (signs B out on the iPhone — fine, its backup is taken), turn on the 64-digit key, *Back up*, `pull`. Cached per WhatsApp version, so usually skipped | adb, Maestro | no |
| `android convert`, `android write` | whatferry | no |
| `pm clear`, `android push`, open WhatsApp, register B, *Restore* with the key typed | adb, whatferry, Maestro | no |
| *Back up*, `pull`, fingerprint, screenshots | Maestro, whatferry, oracle | no |

`roundtrip` runs whichever direction B's current side calls for first, so the
month's state is always consistent. Three registrations a night is nowhere
near WhatsApp's limits at this cadence (a nightly or hourly loop would be:
WhatsApp throttles repeated registrations and bans churned numbers).

One Android detail to prove early: when the template is first made, the
64-digit key is on screen and the harness must read it (`uiautomator dump`
gives the text if it is a TextView; otherwise it is a one-time copy into the
secrets file — a key survives until someone turns encryption off).

### B4. The iPhone's taps — two stages

**Stage 1 (build first).** Every "iOS taps" row is a notified pause:
screenshot, push a notification, wait, `resume`. About ten minutes of tapping
per month. Everything else is already unattended, and this stage is what gives
the first real-phone run of iPhone → Android.

**Stage 2 (only after a spike).** Three independent fixes, each removing one
row:

1. Taps inside WhatsApp and Springboard → Maestro on iOS, which drives
   WebDriverAgent. Needs a paid Apple developer account (free signing expires
   weekly), Developer Mode, `pymobiledevice3 remote tunneld` (root), and
   reinstalling WDA after every restore (`xcodebuild test-without-building`,
   scripted). **Do a one-hour spike before anything else in Stage 2**: install
   WDA, tap one WhatsApp button, restore, reinstall, tap again, on iOS 27. If
   that doesn't work, Stage 1 is the harness.
2. Post-restore panes ("Restore completed", the Apple account sign-in that
   hung on the real transfer) → supervise the test iPhone with Apple
   Configurator and skip the Setup Assistant panes; `cfgutil` can also do the
   restore. One erase, free.
3. Apple ID re-authentication → SIM A in the iPhone as the trusted number, so
   any 2FA code arrives on the phone WDA is driving. This stays the residual
   risk.

### B5. What still needs a person, by design

A WhatsApp update that adds a nudge screen (a few times a year — the same
night the schema check reports the DB changes), an Apple ID prompt the flows
haven't seen, a dead prepaid SIM. The harness never guesses: unknown screen →
screenshot, stop, notify. With a month of slack, needing someone once a
quarter is the target, not a failure.

### B6. Order of work

1. Part A (1 day). Ships to users regardless.
2. Harness skeleton, Android flows, `i2a` with pauses (1–2 days) — first real
   iPhone → Android transfer, the most valuable single result.
3. `a2i` with pauses, oracle, seed corpus, report, timer (1–2 days).
4. WDA spike (half a day) → go / no-go on Stage 2.
5. Stage 2 (1–2 weeks elapsed, mostly debugging the Apple side).

## Running without a Mac (context)

Nothing in whatferry is Mac-only: the backup roots, data folder and adb
discovery branch on the platform, the APFS clone falls back to a copy, restore
goes through usbmuxd (Apple's on Windows via the Apple Devices app or iTunes,
the `usbmuxd` package on Linux), and CI runs the suite on all three systems.
What has never happened is a real restore from Windows or Linux. The known
soft spots are distro `libimobiledevice` lagging iOS releases (Part A removes
it), the full copy instead of a clone, USB drivers on Windows, and udev
rules on Linux.
