# The round-trip harness

Whenever WhatsApp or iOS updates on either test phone, and at least once a
month, with nobody needed except for the iPhone's taps: Android → iPhone,
verify, iPhone → Android, verify, report. It uses whatferry as a
library and touches no phone but the test kit's two. The plan it follows is
[`docs/harness-plan.md`](../docs/harness-plan.md), Part B. At Stage 1, every
tap on the iPhone is a notified pause. With Stage 2 set up (below), the
harness taps the iPhone itself and pauses only when it can't.

It lives beside `src/`, so the whatferry wheel never ships it. It needs no
Python packages beyond whatferry's own, so it has no dependency group.
Maestro and adb are the two outside tools.

## The test kit

Set up once, by hand. First choose the kit's shape with `iphone_accounts` in
the secrets file:

- **2, the default.** The iPhone runs WhatsApp account **A**, and B is added
  next to it as a second account. This tests the second-account move, and
  that the restore leaves the other account untouched. It takes two numbers.
- **1.** B is the iPhone's only WhatsApp account. Each Android → iPhone run
  removes WhatsApp, reinstalls it from the App Store and sets it up as B. This
  tests the move onto an iPhone without WhatsApp, with one SIM.

| | |
|---|---|
| Test iPhone | No passcode, Find My off, Stolen Device Protection off, Auto-Lock Never, iOS auto-update off. Apple ID signed in, so WhatsApp downloads again after a restore and, with one account, after the reinstall. With two accounts, WhatsApp runs **A** as the main account. Paired with the computer: run `whatferry ios backup` once and tap Trust. |
| Pixel | USB debugging on, *Stay awake* on, SIM **B** inside for good, WhatsApp auto-update **on**. The language is English: the flows match English labels. |
| Numbers | B is ferried between the phones, and its SIM never moves: codes for the iPhone are read off the Pixel. With two accounts, A's SIM is needed once, to register A. After that it can stay in a drawer, with WhatsApp's two-step verification PIN on A. Keep every prepaid number alive with a calendar reminder: a recycled number lets a stranger take the account. |
| Computer | An always-on Mac or Linux box, a powered hub, both phones never unplugged. |
| Tools | `mise install` in the repository, Maestro (`curl -fsSL "https://get.maestro.mobile.dev" \| bash`), adb on `PATH`. |

The **seed corpus** is a set of chats on B that every run carries across:
text both ways, a photo with a caption, a video, a voice note, a document, a
contact card, a location, a deleted message, and a group. Make it once on the
Pixel. With two accounts, A replies from the iPhone and is in the group. With
one, any other WhatsApp you own does that part. The first run's
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

## Getting the kit ready

Most of it can be done before the phones arrive:

```sh
mise exec -- uv run python -m harness setup   # the secrets file: passphrase and ntfy topic made up
mise exec -- uv run python -m harness ready   # what's still missing, phones or not
mise exec -- uv run python -m harness ping    # a test notification
```

`setup` never overwrites a secrets file. It makes up the iPhone backup
passphrase and a private ntfy topic; subscribe to that topic in the ntfy app.
`ready` lists every part of the kit: the secrets file, adb, Maestro,
usbmuxd, the phones, notifications, the 64-digit key, Stage 2's
WebDriverAgent and tunnel, the baseline and the daily timer. Each missing
part says what to do. It exits 0 once nothing is missing.

The day the phones arrive:

1. Set each phone up as the table above says, with B's SIM in the Pixel.
2. Plug in **only** the two test phones, then
   `python -m harness setup --detect`. It fills in their IDs, and only
   while those lines are empty. Those become the only phones the harness
   touches, and it clears WhatsApp on them.
3. Write B's number into `number_b`, and set `iphone_accounts`.
4. Make the seed corpus on the Pixel.
5. `python -m harness ready`, then `python -m harness preflight`.
6. Run each Pixel flow once by hand, as [Not built yet](#not-built-yet) says.
7. `python -m harness run`. The first pass records the baseline.
8. Install the daily timer from [`schedule/`](schedule).

## Running it

```sh
mise exec -- uv run python -m harness preflight   # secrets, phones, versions
mise exec -- uv run python -m harness run         # roundtrip; or: run a2i, run i2a
mise exec -- uv run python -m harness watch       # a roundtrip only if something changed (--dry-run: say why)
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
   Then the Pixel sends this run's **check message** to B's own chat, for example
   `whatferry check 2026-11-01 a2i 7f3a`.
3. WhatsApp backs up, the harness copies the backup and the Media folder off, decrypts them and fingerprints them. This is the seed.
4. **Pause:** remove B from WhatsApp on the iPhone.
5. iPhone backup ("before"), and its file list kept.
6. **Pause:** add B on the iPhone. The code arrives on the Pixel, and the harness sends it in a second notification.
7. iPhone backup ("after"). The new account is found from the diff, then converted and written. The schema checks and reports go to `compat/`.
8. Restore, then a wait until the iPhone is back and paired.
9. **Pause:** get past the panes after the restore, open WhatsApp, switch to B.
10. A WhatsApp-only backup is fingerprinted and compared with the seed. The
    run passes only if the check message arrived too. Old chats alone could
    match yesterday's data, so the check message proves this run's transfer
    carried the chats as they are today.

With one account, steps 4 to 7 differ:

4. The harness removes WhatsApp and its data from the iPhone.
5. **Pause:** download WhatsApp again from the App Store. This is skipped if it's already there.
6. **Pause:** set WhatsApp up as B, with the code sent on from the Pixel, skipping the iCloud restore.
7. iPhone backup. B must be the main account, and the chats go into the main database. There is no "before" backup, which saves about an hour.

The rest is the same, with no account to switch to at step 9.

iPhone → Android:

1. Preflight. With Stage 2's taps, the iPhone sends this direction's check
   message to B's own chat. Without them there is none, rather than another
   pause.
2. A WhatsApp-only backup gives B's chats and media, and the seed.
3. The template. It is an empty B on the Pixel: `pm clear`, register, turn on the 64-digit key (read off the screen), back up, copy. It is cached per WhatsApp version, so most months skip it.
4. Convert into the template and write.
5. `pm clear`, push, register B, and restore with the key.
6. Back up, copy, fingerprint, compare, including the check message when one was sent.

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

## The daily timer

[`schedule/`](schedule) has a launchd agent for macOS and a systemd user
timer for Linux. Both run `python -m harness watch` every day at 03:00, and
both catch up when the computer was off. The watch reads WhatsApp's version
on both phones and the iPhone's iOS version. It starts a round trip when any
of them differs from the last passing run, when that run is 30 days old, or
when no run has passed yet. Otherwise it does nothing. While a run waits to
be resumed, the watch only says so: that run's pause has already notified.
So a WhatsApp update is tested the night after it lands, before anyone moves
chats with it. Replace `__REPO__` with the repository's path; each file
says how to install it. A pause exits 75, which systemd counts as success.

## Stage 2: the iPhone's taps

With an `[ios_automation]` table in the secrets file, each iPhone pause
first tries to do the taps itself. That's three pauses with two accounts:
remove B, add B, after the restore. With one account it's also three:
reinstall WhatsApp, set it up as B, after the restore. If anything stops it, the
step falls back to its Stage 1 pause. That covers WebDriverAgent not
starting, a label that differs, or a prompt only a person can answer. The
pause says where the taps stopped, with a screenshot. Stage 2 can't make a
run worse than Stage 1.

Maestro can't drive a physical iPhone, so the harness drives WebDriverAgent
(WDA) itself, through pymobiledevice3 ([`ios_ui.py`](ios_ui.py)). The three
automations are in [`ios_flows.py`](ios_flows.py). Before each one, the
harness puts back what a restore takes away:

- Developer Mode, turned back on without a person when the iPhone has no passcode;
- the developer disk image, mounted again;
- the WDA runner app, installed again from the kit's signed copy.

One-time setup, on a Mac with Xcode:

1. **Developer account.** Join the Apple Developer Program (paid). A free
   account's signature expires every seven days.
2. **Build WDA once**, signed with your team, under a bundle ID of your own:

   ```sh
   git clone https://github.com/appium/WebDriverAgent ~/wda/src
   cd ~/wda/src
   xcodebuild build-for-testing -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner \
     -destination generic/platform=iOS -derivedDataPath ~/wda/build -allowProvisioningUpdates \
     DEVELOPMENT_TEAM=<your team ID> PRODUCT_BUNDLE_IDENTIFIER=be.ariamis.WebDriverAgentRunner
   ```

   Then put this in the secrets file:

   ```toml
   [ios_automation]
   wda_app = "~/wda/build/Build/Products/Debug-iphoneos/WebDriverAgentRunner-Runner.app"
   runner = "be.ariamis.WebDriverAgentRunner.xctrunner"
   ```

   A Linux kit uses the same `.app`, copied over. No Xcode is needed after this.
3. **Developer Mode** on the iPhone: Settings → Privacy & Security →
   Developer Mode. It shows once a developer app has been installed.
4. **The tunnel**, which iOS 17 and later need, runs as root all the time:
   [`schedule/`](schedule) has a launchd daemon and a systemd service for
   `pymobiledevice3 remote tunneld`. It also gives the pauses their
   screenshots.
5. **Supervise the iPhone** with Apple Configurator (free, one erase). Have
   it skip every Setup Assistant pane, so the screens after a restore never
   appear. `preflight` logs whether the phone is supervised.
6. **B's number as the Apple Account's trusted number**, so any sign-in
   code arrives on the Pixel, where you can read it. The harness doesn't read
   Apple's codes, so an Apple Account sign-in still stops the taps and
   becomes a pause. That is the remaining risk the plan names.

Then the go/no-go, which is the plan's spike as two commands:

```sh
mise exec -- uv run python -m harness ios-check     # WDA up, WhatsApp open, one screen read, a screenshot
mise exec -- uv run python -m harness spike --yes   # ios-check, back up, restore that backup, ios-check again
```

`spike` restores the test iPhone from a backup it has just made, so nothing
changes on the phone. After the restore, it checks whether the harness alone
gets WDA working again. If it says go, Stage 2 holds through a real run's
restore.

## Not built yet

- **Nothing has met a real phone.** The Pixel flows follow WhatsApp for
  Android's resource IDs and English labels. Run each once by hand and fix
  what differs: `maestro --device <serial> test harness/flows/<name>.yaml`.
  The iPhone's labels in `ios_flows.py` are written the same way, and the
  first runs will pause where they differ. Adjust the patterns from the
  screenshots.
- **Without the tunnel**, iPhone screenshots work only on iOS 16 and older.
  A pause then says what to do without a picture.
