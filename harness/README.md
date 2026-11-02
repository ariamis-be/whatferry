# The round-trip harness

Once a month, with nobody needed except for the iPhone's taps: Android →
iPhone, verify, iPhone → Android, verify, report. It uses whatferry as a
library and touches no phone but the test kit's two. The plan it follows is
[`docs/harness-plan.md`](../docs/harness-plan.md), Part B, at Stage 1: every
tap on the iPhone is a notified pause.

It lives beside `src/`, so the whatferry wheel never ships it. It needs no
Python packages beyond whatferry's own, so it has no dependency group.
Maestro and adb are the two outside tools.

## The test kit

Set up once, by hand.

| | |
|---|---|
| Test iPhone | No passcode, Find My off, Stolen Device Protection off, Auto-Lock Never, iOS auto-update off. Apple ID signed in, so WhatsApp re-downloads after a restore. WhatsApp with account **A** as the main account. Paired with the computer: run `whatferry ios backup` once and tap Trust. |
| Pixel | USB debugging on, *Stay awake* on, SIM **B** inside for good, WhatsApp auto-update **on**. The language is English: the flows match English labels. |
| Numbers | A stays on the iPhone. B is ferried between the phones. Two prepaid SIMs on real carriers, with a calendar reminder for whatever keeps them alive. |
| Computer | An always-on Mac or Linux box, a powered hub, both phones never unplugged. |
| Tools | `mise install` in the repository, Maestro (`curl -fsSL "https://get.maestro.mobile.dev" \| bash`), adb on `PATH`. |

The **seed corpus** is a set of chats on B that every run carries across:
text both ways, a photo with a caption, a video, a voice note, a document, a
contact card, a location, a deleted message, and a group of A and B. Make it
once on the Pixel, with A replying from the iPhone. The first run's
fingerprint of it becomes `baseline.json`, and every later run also reports
what the baseline had that the result lacks.

The **secrets file**, `~/.config/whatferry-harness/secrets.toml`, mode 600,
is described in [`config.py`](config.py). It holds the iPhone backup
passphrase, B's number written `+<country code> <number>`, the two phones'
IDs, B's 64-digit key, and where to notify (an ntfy topic, mail, or both).
Before the first run, turn on B's end-to-end encrypted backup on the Pixel
with a 64-digit key and copy the key in. Later runs keep it up to date
themselves.

The harness keeps everything in `~/whatferry-harness`. That covers the runs,
the Android templates, `kit.json` (which phone holds B), `baseline.json`, and
a whatferry folder of its own. Its backups and decrypted copies never mix
with anyone else's: `WHATFERRY_HOME` and `WHATFERRY_BACKUP_ROOT` point
there for the run.

## Running it

```sh
mise exec -- uv run python -m harness preflight   # secrets, phones, versions
mise exec -- uv run python -m harness run         # roundtrip; or: run a2i, run i2a
mise exec -- uv run python -m harness status
mise exec -- uv run python -m harness resume      # after a pause or a fix
mise exec -- uv run python -m harness abandon     # give up a run, so a new one can start
mise exec -- uv run python -m harness code        # B's newest WhatsApp code, from the Pixel
```

| Exit code | Meaning |
|---|---|
| 0 | passed |
| 1 | failed: the notification says at which step, with a screenshot |
| 2 | refused to start: secrets, a phone not on the list, or a run waiting to be resumed |
| 75 | paused for a person |

Every start checks that the two phones are the kit's and that no other phone
is connected. `roundtrip` begins with the direction B's side calls for, so
B always ends on the phone it started on.

## What a run does

Android → iPhone:

1. Preflight: the phones, and the WhatsApp and iOS versions, logged.
2. B registered on the Pixel; if not, registered, with WhatsApp reading the SMS itself.
3. WhatsApp backs up, the harness copies the backup and the Media folder off, decrypts them and fingerprints them. This is the seed.
4. **Pause:** remove B from WhatsApp on the iPhone.
5. iPhone backup ("before"), and its file list kept.
6. **Pause:** add B on the iPhone. The code arrives on the Pixel, and the harness sends it in a second notification.
7. iPhone backup ("after"). The new account is found from the diff, then converted and written. The schema checks and reports go to `compat/`.
8. Restore, then a wait until the iPhone is back and paired.
9. **Pause:** get past the panes after the restore, open WhatsApp, switch to B.
10. A WhatsApp-only backup is fingerprinted and compared with the seed.

iPhone → Android:

1. Preflight.
2. A WhatsApp-only backup gives B's chats and media, and the seed.
3. The template. It is an empty B on the Pixel: `pm clear`, register, turn on the 64-digit key (read off the screen), back up, copy. It is cached per WhatsApp version, so most months skip it.
4. Convert into the template and write.
5. `pm clear`, push, register B, and restore with the key.
6. Back up, copy, fingerprint, compare.

A step that meets a screen it doesn't know stops the run. It takes a
screenshot of both phones and notifies. The harness never guesses. `resume`
after fixing re-runs that step. Steps already done are never repeated.

## Is it the same? The oracle

[`oracle.py`](oracle.py) fingerprints every message whatferry carries by
WhatsApp's own message ID. The fingerprint records each message's chat, kind,
time to the millisecond, a hash of its text or caption, and a hash of its
media file, read from the file itself. A passing run diffs to zero. Calls,
system lines, polls and the other kinds whatferry has no counterpart for are
counted as known losses and never fail a run. Reactions and quoted-reply links
are not messages of their own, so they never enter the fingerprint. Chats show
by their last four digits only.

## The run folder

`runs/<date>/` holds `state.json`, `log.txt` and `maestro.log`. It also holds
`screenshots/`, every one numbered, and `compat/`, the schema checks and the
conversion and write reports. Then come `fingerprints/`, `a2i-diff.json`,
`i2a-diff.json` and `summary.txt`, the line the notification sent.

## The monthly timer

[`schedule/`](schedule) has a launchd agent for macOS and a systemd user
timer for Linux. Both fire on the 1st at 03:00, and both catch up when the
computer was off. Replace `__REPO__` with the repository's path; each file
says how to install it. A pause exits 75, which systemd counts as success.

## Not built yet

- **The flows haven't met a real Pixel.** They follow WhatsApp for Android's
  resource IDs and English labels. Run each once by hand and fix what
  differs: `maestro --device <serial> test harness/flows/<name>.yaml`. That is
  the first job of the plan's step 2.
- **iPhone screenshots** need a developer disk image on the phone. Without
  one, a pause says what to do without a picture.
- **Stage 2**, which takes the iPhone's taps out of the pauses, waits on the
  one-hour WebDriverAgent spike the plan describes. It needs a paid Apple
  developer account and the real iPhone.
