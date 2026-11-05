// English is the shape every other language fills: a missing key fails the build.
import type { ReactNode } from "react"

import { Code } from "@/components/code"

export type Platform = "darwin" | "win32" | "other"

export const en = {
  header: {
    tagline: "Stays on this computer · writes to a phone only at the end, when you say",
    language: "Language",
    theme: "Theme",
    light: "Light",
    dark: "Dark",
    system: "System",
  },
  // Short: nine of them share the width of the page.
  steps: {
    start: "Start",
    android: "Android",
    before: "iPhone",
    account: "Account",
    after: "Compare",
    convert: "Convert",
    write: "Write",
    restore: "Restore",
    copy: "Copy",
    done: "Results",
  },
  stepOf: (n: number, total: number) => `Step ${n} of ${total}`,
  stepLabel: (n: number, title: string, done: boolean) => `Step ${n}: ${title}${done ? " (done)" : ""}`,
  stepSkipped: "not needed",
  nav: { back: "Back", continue: "Continue", start: "Start", first: (step: string) => `${step} first` },
  common: {
    loading: "Loading…",
    openWithLink: "Open the wizard with the link `whatferry ui` printed.",
    cantReach: (m: string) => `Can't reach whatferry: ${m}. Is \`whatferry ui\` still running?`,
    failed: "That didn't work",
    checked: "Checked",
    searchAgain: "Search again",
    messagesRange: (a: string, b: string): ReactNode => (
      <>
        Messages from <strong>{a}</strong> to <strong>{b}</strong>.
      </>
    ),
    noMessages: "No messages yet.",
  },
  counts: {
    chats: "chats",
    messages: "messages",
    media: "media",
    "quoted replies": "quoted replies",
    "reactions and other add-ons": "reactions and other add-ons",
    "contact cards": "contact cards",
    locations: "locations",
    calls: "calls",
    "contacts and groups (jid)": "contacts and groups (jid)",
    "group members": "group members",
    "group info": "group info",
    "message info (receipts)": "message info (receipts)",
    "profile push names": "profile names",
    "files added": "files added",
    "files changed": "files changed",
    "files removed": "files removed",
    "chats matched": "chats already there",
    "chats created": "chats added",
    "media placed": "media files placed",
    "media missing": "media files not found",
  } as Record<string, string>,
  start: {
    title: "Move WhatsApp chats from Android to iPhone",
    titleToAndroid: "Move WhatsApp chats from iPhone to Android",
    lead: "This wizard moves one Android WhatsApp account's chats into WhatsApp on your iPhone, without erasing the iPhone. Your backups are only read; the iPhone is written to once, at the end, when you choose to restore.",
    leadToAndroid: "This wizard moves one iPhone WhatsApp account's chats into WhatsApp on your Android phone. Your backups are only read; the Android phone is written to once, at the end, when you copy the new backup onto it.",
    directionTitle: "Which way",
    android: "Android",
    iphone: "iPhone",
    directionNote: {
      "to-iphone": "Into WhatsApp on an iPhone that's already set up, as its second account or its only one.",
      "to-android": "Into WhatsApp on an Android phone, through WhatsApp's own restore from a backup.",
    },
    needsToAndroid: [
      "The iPhone, with WhatsApp and the chats you want to move.",
      "The Android phone, with WhatsApp signed in to the number you're moving.",
      "A cable for each phone, and USB debugging on the Android phone.",
      "About an hour, mostly waiting for backups. You can close this and come back: progress is saved.",
    ],
    happensToAndroid: [
      "Back up the iPhone, so the wizard can read the account's chats, photos and videos.",
      "Make WhatsApp's encrypted backup on the Android phone, with a 64-digit key, and bring the file here.",
      "Convert the iPhone chats into that backup and look through a preview of the result.",
      "Write the new backup, copy it onto the Android phone, and restore it in WhatsApp with the key.",
    ],
    needTitle: "You'll need",
    needs: [
      "The Android phone, with WhatsApp and the chats you want to move.",
      "The iPhone, with WhatsApp already set up for its own number.",
      "A cable to connect the iPhone to this computer.",
      "About an hour, mostly waiting for backups. You can close this and come back: progress is saved.",
    ],
    happensTitle: "What happens",
    happens: [
      "Make an encrypted WhatsApp backup on the Android phone and bring the file here.",
      "Back up the iPhone, so the wizard can see how WhatsApp stores your current account.",
      "Add the Android number to WhatsApp on the iPhone as a second account.",
      "Back up the iPhone again. Comparing the two backups shows exactly where the new account's chats will go.",
      "Convert the Android chats and look through a preview of the result.",
      "Write a new copy of the iPhone backup with the chats in it, then restore it onto the iPhone.",
    ],
    privateTitle: "What stays private",
    privateLead: "Nothing leaves this computer.",
    private: (home: string): ReactNode[] => [
      "The page only talks to whatferry on this computer. Nothing is uploaded anywhere.",
      "Keys and passphrases are used once and never saved.",
      <>
        Decrypted copies are kept in <Code>{home}</Code>, readable only by you. Delete it when you're done.
      </>,
    ],
  },
  android: {
    title: "Android backup",
    lead: "WhatsApp's encrypted backup, with a 64-digit key you write down, can be read here without rooting the phone.",
    makeTitle: "Make the backup on the Android phone",
    make: [
      "Open WhatsApp → Settings → Chats → Chat backup → End-to-end encrypted backup → Turn on.",
      "Choose “Use 64-digit encryption key instead”, then generate the key. Write it down or take a screenshot: WhatsApp can't show it again.",
      "Back on Chat backup, tap Back up. This saves a file on the phone even if Google Drive backups are off.",
    ],
    toAndroidTitle: "First, WhatsApp on the Android phone",
    toAndroidBody: "Install WhatsApp and sign in with the number you're moving. If it offers to restore a backup, skip it. Then make the backup below: it gives the wizard WhatsApp's own empty database for the account, which the iPhone chats go into.",
    multiTitle: "More than one WhatsApp account on the phone?",
    multiBody: "Each account has its own backup and its own key. Switch to the account you want to move (tap your profile picture → switch account) before the steps above, and repeat them for each account you want.",
    bringTitle: "Bring the file to this computer",
    bringLead: "Any of these works; pick whichever is easiest.",
    tabs: { share: "Share from the phone", cable: "USB file transfer", adb: "Copy with USB debugging" },
    share: [
      <>
        Open the phone's Files app (Files by Google, or My Files on Samsung) and go to{" "}
        <Code>Android/media/com.whatsapp/WhatsApp</Code>. Some file apps hide the <Code>Android</Code> folder; Files by
        Google shows it.
      </>,
      <>
        Open <Code>Databases</Code>, or with several accounts <Code>accounts</Code> → the account's number →{" "}
        <Code>Databases</Code>.
      </>,
      <>
        Long-press <Code>msgstore.db.crypt15</Code> (the one without a date) and tap Share.
      </>,
      "Send it to this computer, with whatever you have: LocalSend (free, phone and computer on the same Wi-Fi, nothing goes online), Quick Share (Windows), Google Drive, or email or a message to yourself.",
      "Save it in Downloads, then click Search again below.",
    ] as ReactNode[],
    cable: (platform: Platform): string[] => [
      "Plug the phone into this computer with a USB cable and unlock it.",
      "On the phone, tap the “Charging this device via USB” notification and choose File transfer.",
      {
        darwin: "A Mac can't open Android phones on its own: install OpenMTP (free, openmtp.ganeshrvel.com) and open the phone in it.",
        win32: "Open File Explorer: the phone appears under This PC.",
        other: "Your file manager shows the phone in its sidebar.",
      }[platform],
      "Copy msgstore.db.crypt15 from the folder below into Downloads, then click Search again below.",
    ],
    foldersTitle: "Where WhatsApp keeps backups on the phone",
    folders: ["One account", "Several accounts", "WhatsApp Business", "Android 10 or older"],
    foldersNote: (
      <>
        With several accounts, each <Code>accounts/&lt;number&gt;</Code> folder is one account: pick the one whose
        msgstore.db.crypt15 is newest, just after you tapped Back up. Files ending .crypt14 and dated or “increment”
        files can't be used.
      </>
    ),
    chooseTitle: "Choose the file",
    searching: "Searching…",
    noneFound: "No WhatsApp backup found yet.",
    chooseFile: "Choose a file…",
    copyingFile: (name: string) => `Copying ${name}…`,
    searchHint: (folders: ReactNode): ReactNode => (
      <>Search again looks for WhatsApp backups in {folders}. Elsewhere? Use Choose a file.</>
    ),
    listAnd: " and ",
    listSep: ", ",
    keyTitle: "Enter the key",
    keyLabel: "64-digit key",
    keyPlaceholder: "64 characters, spaces are fine",
    showKey: "Show key",
    hideKey: "Hide key",
    keyHint: "Used once to decrypt, then forgotten. Not needed if you picked an already decrypted msgstore.db.",
    decrypting: "Decrypting and checking the backup…",
    decrypt: "Decrypt and check",
    checkAgain: "Check again",
    resultLine: (version: string, db: number, checked: string) =>
      `WhatsApp ${version} · database version ${db} · checked ${checked}`,
    legacy: "This backup uses WhatsApp's old layout. Update WhatsApp on the phone and back up again.",
    jidTitle: "Contact identifiers by type",
    jidHead: ["Server", "Count"],
    decryptedCopy: "Decrypted copy:",
    accountsTitle: "Android accounts",
    accountsLead: "Each account is moved on its own. To add another, choose its backup file below and decrypt it; switch here to work on one.",
    accountRow: (ends: string | null, messages: string) => `Number ending ${ends ?? "?"} · ${messages} messages`,
    accountProgress: (destination: string | null, secondDone: boolean) =>
      [destination ? `goes to: ${destination}` : "destination not chosen yet", secondDone ? "second backup checked" : null]
        .filter(Boolean).join(" · "),
    destinationNames: { setup: "set up WhatsApp", second: "second account", existing: "existing account" } as Record<string, string>,
    workingOn: "Working on this one",
    switchTo: "Switch to this account",
    movingAccount: (ends: string | null) => `Android account ending ${ends ?? "?"}`,
  },
  phone: {
    intro: (folder: string): ReactNode => (
      <>
        Plug the phone into this computer and whatferry copies the backup itself, straight into <Code>{folder}</Code>.
        Needs USB debugging on the phone and adb on this computer; you can turn debugging off again afterwards.
      </>
    ),
    looking: "Looking for adb and connected phones…",
    noAdbTitle: "adb isn't installed on this computer",
    noAdbIntro: "adb is Google's free tool for talking to Android phones over USB.",
    install: {
      darwin: ["With Homebrew: brew install --cask android-platform-tools", "Or download platform-tools from Google (below) and unzip it."],
      win32: ["In a terminal: winget install Google.PlatformTools", "Or download platform-tools from Google (below) and unzip it."],
      other: ["Debian or Ubuntu: sudo apt install adb · Fedora: sudo dnf install android-tools", "Or download platform-tools from Google (below) and unzip it."],
    } as Record<Platform, string[]>,
    download: (
      <>
        Google's download: <Code>developer.android.com/tools/releases/platform-tools</Code>. If adb is somewhere whatferry
        doesn't look, start it with <Code>WHATFERRY_ADB=/path/to/adb</Code>.
      </>
    ),
    debugTitle: "Turn on USB debugging",
    debug: [
      "On the phone, open Settings → About phone and tap Build number seven times. Enter your PIN if asked; it says “You are now a developer”. (Samsung: Settings → About phone → Software information → Build number.)",
      "Go back to Settings → System → Developer options and turn on USB debugging.",
      "Plug the phone into this computer with a USB cable and unlock it.",
      "Tap Allow on “Allow USB debugging?”. Ticking “Always allow from this computer” saves doing it again.",
      "Click Find phone below.",
    ],
    debugOff: "When you're done: Developer options → turn USB debugging off.",
    notReady: (model: string) => `${model} isn't ready`,
    advice: {
      unauthorized: "Unlock the phone and tap Allow on “Allow USB debugging?”.",
      offline: "The phone isn't answering: unplug it, plug it back in, and unlock it.",
      "no permissions": "This computer isn't allowed to talk to the phone (on Linux, add a udev rule for Android).",
      authorizing: "Waiting for you to tap Allow on the phone.",
    } as Record<string, string>,
    otherState: (state: string) => `adb says “${state}”.`,
    phone: "Android phone",
    connected: "Connected",
    account: (app: string, account: string | null) => (account ? `${app} · account ${account}` : app),
    noBackups: "No WhatsApp backup on this phone yet. Make one first (step 1), then click Find phone again.",
    noUsable: "No usable backup yet: turn on the 64-digit encrypted backup and tap Back up (step 1), then click Find phone again.",
    otherFiles: (n: number) => `${n} other ${n === 1 ? "file" : "files"} that can't be used`,
    notes: {
      rooted: "Older encryption: its key only exists on a rooted phone. Turn on the 64-digit encrypted backup and back up again to get a .crypt15 file.",
      increment: "A partial (incremental) backup; use the full msgstore file.",
      other: "Not a WhatsApp chat backup.",
    },
    copy: "Copy",
    copying: "Copying…",
    copiedTitle: (name: string) => `Copied ${name}`,
    copiedBody: "It's chosen below, in step 3.",
    findPhone: "Find phone",
  },
  backup: {
    title: { before: "iPhone backup", after: "Second iPhone backup" },
    lead: {
      before: "A backup shows how WhatsApp on the iPhone stores its data today. The wizard reads it; it never changes it.",
      after: "With the second account added, a new backup shows which files the new account created. That's where the Android chats will go.",
    },
    needFirst: "Check the first iPhone backup before this one.",
    goFirst: "Go to the first backup",
    makeTitle: { before: "Back up the iPhone", after: "Back up the iPhone again" },
    make: {
      darwin: [
        "Connect the iPhone to this Mac with a cable and unlock it. Tap Trust if it asks.",
        "Open Finder and select the iPhone in the sidebar.",
        "Under Backups, choose “Back up all of the data on your iPhone to this Mac”.",
        "Tick “Encrypt local backup” and choose a passphrase you will remember. You'll type it here in a moment.",
        "Click Back Up Now and wait until it finishes.",
      ],
      win32: [
        "Connect the iPhone to this PC with a cable and unlock it. Tap Trust if it asks.",
        "Open the Apple Devices app (or iTunes) and select the iPhone.",
        "Under Backups, choose “Back up all of the data on your iPhone to this computer”.",
        "Tick “Encrypt local backup” and choose a passphrase you will remember. You'll type it here in a moment.",
        "Click Back Up Now and wait until it finishes.",
      ],
      other: [
        "Install libimobiledevice and connect the iPhone with a cable. Unlock it and tap Trust.",
        "Turn on encryption once: idevicebackup2 encryption on",
        "Make the backup: idevicebackup2 backup --full <folder>",
        "Start the wizard with WHATFERRY_BACKUP_ROOT=<folder> so it can find the backup.",
      ],
    } as Record<Platform, string[]>,
    now: {
      title: "Back up now",
      lead: "whatferry makes the backup over the cable itself, as Finder does. Connect the iPhone with a cable and unlock it.",
      looking: "Looking for the iPhone…",
      connect: "No iPhone found. Connect it with a cable, unlock it, then look again.",
      onlyOne: "More than one iPhone is connected: leave only the one to back up.",
      trust: "The iPhone doesn't trust this computer yet. Back up now asks it: tap Trust on the phone, then back up again.",
      found: (name: string) => `Found ${name}.`,
      encrypts: "Its backups are encrypted.",
      turnOnTitle: "This iPhone doesn't encrypt its backups yet",
      turnOnBody: "WhatsApp's chats are only in an encrypted backup. Choose a passphrase: the iPhone encrypts every backup with it from now on, and Finder shows “Encrypt local backup” ticked. The iPhone may ask for its passcode.",
      choose: "Choose a backup passphrase",
      again: "Type it again",
      mismatch: "The two don't match.",
      run: "Back up now",
      lookAgain: "Look again",
      working: (p: number) => `Backing up… ${Math.round(p)}%`,
      keepConnected: "This can take an hour for a full iPhone. Keep it connected and unlocked.",
      done: "Backed up",
      turnedOn: "Encryption is now on for this iPhone. Keep the passphrase: no backup of it opens without it.",
      byHand: "Or back up by hand",
    },
    samePassphrase: "Use the same passphrase as before. The new backup replaces the old one in the same folder; the wizard kept what it needs from the first.",
    chooseTitle: "Choose the backup",
    looking: "Looking for backups…",
    noneTitle: "No backups found yet",
    lookedIn: (folders: string) => `Looked in ${folders}.`,
    noRoot: "This system has no standard backup folder: set WHATFERRY_BACKUP_ROOT.",
    encrypted: "Encrypted",
    notEncrypted: "Not encrypted",
    iphone: "iPhone",
    deviceLine: (model: string, ios: string, date: string) => `${model} · iOS ${ios} · backed up ${date}`,
    notEncryptedTitle: "This backup isn't encrypted",
    notEncryptedBody: "It's fine for checking, but the transfer will need an encrypted one: tick “Encrypt local backup” and back up again.",
    passLabel: "Backup passphrase",
    passHint: "The one you chose when you ticked “Encrypt local backup”. Used once, never saved.",
    unlocking: "Unlocking the backup. This takes a minute or two: the slow part is the encryption doing its job.",
    reading: "Reading the backup…",
    check: { before: "Check this backup", after: "Check and compare" },
    checkAgain: "Check again",
    resultLine: (model: string, ios: string, backed: string, checked: string) =>
      `${model} · iOS ${ios} · backed up ${backed} · checked ${checked}`,
    noWhatsapp: "This backup has no WhatsApp data. Is WhatsApp installed on this iPhone?",
    chatsIn: (path: string): ReactNode => (
      <>
        Chats in <code className="font-mono text-xs">{path}</code>
      </>
    ),
    messagesRange: (a: string, b: string) => `Messages from ${a} to ${b}`,
    manyStores: (n: number) => `${n} chat databases: probably one per account.`,
    areasTitle: "WhatsApp's storage areas",
    areasHead: ["Area", "Files", "Size"],
    savedList: "Saved this backup's file list, to compare with the next backup.",
    diffTitle: "What adding the account changed",
    foundOne: "Found the new account's chat database",
    foundMany: (n: number) => `Found ${n} new chat databases`,
    whereGo: "That's where the Android chats will go.",
    noneNewTitle: "No new chat database appeared",
    noneNewBody: "The second account may share the existing one, or WhatsApp hadn't finished setting it up before the backup. The full list of changes is below.",
    diffHead: ["Where", "Added", "Changed", "Removed"],
    filesAdded: "Files added",
    filesChanged: "Files changed",
  },
  destination: {
    title: "Where should the Android chats go?",
    lead: "Choose which WhatsApp account on this iPhone receives them. The suggestion comes from what the backups show.",
    suggested: "Suggested",
    options: {
      setup: {
        title: "Set up WhatsApp on this iPhone with the Android number",
        body: "WhatsApp isn't set up on this iPhone yet: the Android number becomes its only account.",
      },
      second: {
        title: "Add the Android number as a second account",
        body: "The iPhone keeps its current account; the Android chats go into a new, empty one beside it.",
      },
      existing: {
        title: "An account here already uses the Android number",
        body: "The Android chats go into that account. If it already has chats, the two histories are merged.",
      },
    },
    reasons: {
      noWhatsapp: "This backup has no WhatsApp data.",
      matches: (ends: string) =>
        `An account here has a number ending in ${ends}, like the Android backup's (only the last two digits are known, so check it's really the same number).`,
      different: (ends: string, accounts: string) =>
        `The Android number ends in ${ends}; this iPhone's account numbers end in ${accounts}.`,
      unknown: "The Android backup doesn't record its number, so the wizard can't compare.",
      stale: "This iPhone check was saved with an older way of reading the iPhone's accounts, which could mistake a chat for an account. Click Check again above to compare the numbers.",
      secondStarted: (ends: string) =>
        `The Android number (ending ${ends}) is already set up here as a second account, but it has no chats yet: signing in probably stopped before the confirmation code. Finish signing in on the iPhone, then make the second backup.`,
      iphoneUnknown: (ends: string) =>
        `The Android number ends in ${ends}, but the iPhone's account numbers couldn't be read from this backup.`,
    },
    full: "This iPhone may already have a second WhatsApp account: the backup has a folder for one. If so, WhatsApp may not allow a third, and you may have to remove one first.",
    merge: (n: string) =>
      `That account already has ${n} messages on this iPhone. Merging keeps both histories, but it's the hardest case to get right.`,
    notMatching: (ends: string, numbers: string) =>
      `No account here has a number ending in ${ends}. With this choice the Android chats go into an account with a different number (ending ${numbers}), and they will appear under that number.`,
    cantConfirm: "The wizard can't confirm that an account here uses the Android number: check WhatsApp on the iPhone before choosing this.",
    replaceExisting: (numbers: string | null) =>
      `WhatsApp is already set up on this iPhone${numbers ? ` (number ending ${numbers})` : ""}. Setting it up again with the Android number would sign that account out; add a second account instead to keep it.`,
    accountsTitle: "WhatsApp accounts on this iPhone",
    account: (numberEnds: string | null, country: string | null, main: boolean, hasChats: boolean) =>
      `Number ending ${numberEnds ?? "?"}${country ? ` (${country})` : ""} · ${main ? "main account" : "second account"}${hasChats ? "" : " · no chats in this backup"}`,
    secondNoChats: "That account's chats aren't in the iPhone backup: either it has none yet, or WhatsApp keeps a second account's chats out of backups. The transfer has to work around that, so it's the next thing to find out.",
    folders: (n: number) =>
      `The backup also has ${n} ${n === 1 ? "folder" : "folders"} WhatsApp keeps for another account, possibly a second one; its number can't be read.`,
    chooseFirst: "Check the iPhone backup first; then choose where the chats go.",
  },
  account: {
    setup: {
      title: "Set up WhatsApp with the Android number",
      lead: "WhatsApp creates its database, folders and keys for the Android number. The next backup shows where they are.",
      sectionTitle: "Set up WhatsApp on the iPhone",
      steps: [
        "Install WhatsApp from the App Store, if it isn't installed.",
        "Open it and register the Android phone's number; enter the code WhatsApp sends. WhatsApp on the Android phone signs out: that's expected, and your backup file is already safe on this computer.",
        "If WhatsApp offers to restore chats, skip it. The account should start empty.",
      ],
    },
    existing: {
      title: "Nothing to add on the iPhone",
      lead: "The account that already uses the Android number takes the chats. A second backup isn't needed: continue to the results.",
    },
    none: "Choose where the chats go first: it's at the end of the iPhone backup step.",
    goChoose: "Choose where the chats go",
    notNeeded: "Not needed for this choice",
    skipNote: "The account that takes the chats already exists, so there's nothing new to find. Continue to the results.",
    title: "Add the Android number on the iPhone",
    lead: "WhatsApp sets up the second account itself: its own empty database, folders and keys. Later, only that new account is filled with the Android chats; your current account isn't touched.",
    addTitle: "Add the account on the iPhone",
    steps: [
      "On the iPhone, open WhatsApp → Settings and choose Add account (next to your name at the top).",
      "Register the Android phone's number and enter the code WhatsApp sends. WhatsApp on the Android phone signs out: that's expected, and your backup file is already safe on this computer.",
      "If WhatsApp offers to restore chats for the new account, skip it. The new account should start empty.",
    ],
    keepAndroid: "Keep WhatsApp installed on the Android phone until the transfer is finished. If anything goes wrong you can sign back in there and your chats are still on it.",
  },
  convert: {
    title: "Convert the chats",
    lead: "Merges the Android account's history into a copy of the iPhone account's chat database. Nothing on either phone, or in the backup, changes yet: look through the result below before writing, and convert again with another choice if it's not right.",
    needBackups: "Check the Android backup and an iPhone backup first.",
    goAndroid: "Go to the Android backup",
    goIphone: "Go to the iPhone backup",
    targetTitle: "Which iPhone account gets the chats",
    leadToAndroid: "Merges the iPhone account's history into a copy of the Android account's chat database. Nothing on either phone, or in either backup, changes yet: look through the result below before writing, and convert again with another choice if it's not right.",
    sourceTitle: "Which iPhone account's chats move",
    fromIphoneBackup: (date: string) => `From the iPhone backup checked ${date}.`,
    mediaFromBackup: "From the iPhone backup",
    mediaFromBackupNote: "Photos, videos, voice notes and documents the iPhone has, taken out of its backup. Older ones WhatsApp has offloaded from the iPhone aren't there to take.",
    androidNotWritableTitle: "The Android backup can't be written back",
    androidNotWritable: "Check WhatsApp's end-to-end encrypted backup (msgstore.db.crypt15, with its 64-digit key) on the Android step: that's the one WhatsApp restores from.",
    notYetToAndroid: "Replies, reactions, polls and calls aren't carried over yet; the messages themselves are.",
    versionTitle: (kind: string) => `Not the ${kind} WhatsApp version whatferry was checked on`,
    fromBackup: (second: boolean, date: string) =>
      `From the ${second ? "second" : "first"} iPhone backup, checked ${date}.`,
    mainAccount: (ends: string | null) => `Main account${ends ? `, number ending ${ends}` : ""}`,
    otherAccount: (ends: string | null) => `Added account${ends ? `, number ending ${ends}` : ""}`,
    suggested: "Suggested",
    hasMessages: (n: string) => `${n} message${n === "1" ? "" : "s"} there now`,
    mergeNote: (n: string) =>
      `This account already has ${n} message${n === "1" ? "" : "s"}. The Android chats are added alongside them; chats with the same person or group are joined.`,
    mediaTitle: "Photos, videos and voice notes",
    mediaLead: "The Android WhatsApp Media folder, copied to this computer. Each folder found is checked against the newest files the Android chats name.",
    mediaFound: (found: number, sampled: number) =>
      sampled ? `Has ${found} of the ${sampled} newest files the chats name` : "The chats name no media files",
    mediaOther: "Another folder",
    mediaPlaceholder: "Path to a copy of WhatsApp/Media",
    mediaNone: "Without media",
    mediaNoneNote: "Messages keep their captions; the photos and videos themselves stay behind.",
    working: "Converting… a minute or two.",
    run: "Convert",
    again: "Convert again",
    doneTitle: (converted: string, total: string) => `${converted} of ${total} messages converted`,
    doneLine: (at: string) => `Converted ${at}.`,
    checksClean: "The merged database passed every consistency check.",
    checksFailed: "The merged database failed a consistency check",
    integrity: (result: string) => `integrity: ${result}`,
    skipped: (n: string) =>
      `${n} event${n === "1" ? "" : "s"} WhatsApp keeps differently on each phone (system notices, calls, polls and the like) ${n === "1" ? "is" : "are"} left out.`,
    notYet: (what: string, n: string) => `${what}: ${n}, not carried over yet (the messages themselves are).`,
  },
  preview: {
    title: "What the account will have",
    loading: "Reading the result…",
    // `from` is where the moved messages come from: android or iphone below.
    android: "Android",
    iphone: "the iPhone",
    totals: (fresh: string, joined: string, unchanged: string, messages: string, from: string) =>
      `${fresh} new chat${fresh === "1" ? "" : "s"} and ${joined} joined with chats already there (${messages} message${messages === "1" ? "" : "s"} from ${from}); ${unchanged} chat${unchanged === "1" ? "" : "s"} untouched.`,
    fromSource: (from: string) => `From ${from}`,
    all: "All chats",
    search: "Search by name or number",
    noChats: "No chats match.",
    group: "Group",
    change: { new: "New", joined: "Joined", unchanged: "Untouched" },
    chatLine: (moved: string, total: string, first: string, last: string, from: string) =>
      `${moved} of ${total} messages from ${from} · ${first} to ${last}`,
    showAll: (n: string) => `Show all ${n}`,
    newest: (n: string, from: string) => `newest messages of ${n}; outlined ones come from ${from}`,
    kinds: {
      image: "Photo",
      video: "Video",
      audio: "Voice message or audio",
      contact: "Contact card",
      location: "Location",
      document: "Document",
      gif: "GIF",
      sticker: "Sticker",
      deleted: "This message was deleted",
      link: "Link",
      system: "Chat event",
      other: "Other message",
    } as Record<string, string>,
  },
  write: {
    title: "Write a new backup",
    lead: "Copies the iPhone backup and puts the converted chats into the copy, encrypted as iOS does it. Every file written is read back and checked.",
    needConvert: "Convert the chats first.",
    goConvert: "Go to Convert",
    fromTitle: "The backup it starts from",
    from: (date: string) => `The iPhone backup from ${date}, which the chats were converted into:`,
    untouched: "That backup stays as it is; the new one goes into whatferry's own folder.",
    previewFirst: "What gets written is the conversion as its preview shows it.",
    openPreview: "Look through the preview",
    passTitle: "Passphrase",
    leadToAndroid: "Encrypts the converted database as WhatsApp's own backup, under the Android backup's 64-digit key, and lays it out with the photos and videos as WhatsApp keeps them. It's decrypted again and checked.",
    fromAndroid: "The Android backup the chats were converted into:",
    keyTitle: "The Android backup's key",
    keyLabel: "64-digit key",
    keyHint: "The key WhatsApp showed when you turned on the end-to-end encrypted backup. Used once, never saved.",
    skipNoteToAndroid: "Normally refused: the Android backup must be the one the chats were converted into. With this, whatever WhatsApp on the Android phone got after that backup is lost when you restore.",
    changedBodyToAndroid: "Check the newest Android backup again on its step, then convert again. That keeps everything the account has now.",
    addedToAndroid: (bytes: string, media: string) =>
      `msgstore.db.crypt15 (${bytes}), decrypted again and verified, and ${media} media files, ready to copy to the phone.`,
    noPass: "This backup isn't encrypted: no passphrase needed.",
    skipLabel: "Write even if the backup changed since converting",
    skipNote: "Normally refused: the backup must be the one the chats were converted into. With this, whatever the account got on the iPhone after converting is lost when you restore.",
    changedTitle: "This backup changed after converting",
    changedBody: "Check the newest iPhone backup again on its step, then convert again. That keeps everything the account has now.",
    working: "Writing… a few minutes for a large backup.",
    run: "Write the new backup",
    again: "Write again",
    doneTitle: "New backup written and checked",
    unchecked: "source not checked",
    doneLine: (at: string) => `Written ${at}.`,
    added: (files: string, bytes: string, verified: string) =>
      `${files} files added (${bytes}); ${verified} files read back and verified.`,
  },
  copy: {
    title: "Copy onto the Android phone",
    lead: "Puts the new backup and its media into WhatsApp's folder on the phone over USB. Then WhatsApp restores it, as it would any backup of its own.",
    warnTitle: "WhatsApp on the Android phone starts over from this backup",
    warnBody: "Restoring replaces WhatsApp's chats on the Android phone with the backup's: the account's own chats as they were at its backup, plus the ones from the iPhone. Nothing else on the phone changes.",
    beforeTitle: "Before you start",
    before: [
      "If anything arrived in WhatsApp on the Android phone since the backup you checked, back up again and go through the Android step, Convert and Write again.",
      "Clear WhatsApp's data: Settings → Apps → WhatsApp → Storage → Clear storage. WhatsApp signs out on this phone; the chats come back from the backup.",
      "Connect the phone with a cable, USB debugging on (as on the Android step), and unlock it.",
    ] as ReactNode[],
    phoneTitle: "The Android phone",
    looking: "Looking for the phone…",
    noAdbTitle: "adb isn't installed",
    noAdb: "Install it as the Android step explains, or copy the folder by hand (below).",
    noPhoneTitle: "No phone found",
    noPhone: "Connect the phone with a cable, turn on USB debugging, unlock it, and look again.",
    ready: "Ready",
    whichFolder: "Which WhatsApp folder on the phone (one per account):",
    lookAgain: "Look again",
    confirmTitle: "Confirm",
    cleared: "I cleared WhatsApp's storage on the phone (step 1.2).",
    working: "Copying… a few minutes with many photos.",
    run: "Copy onto the phone",
    again: "Copy again",
    doneTitle: "Copied onto the phone",
    doneLine: (at: string, media: string) => `Copied ${at}, with ${media} media files. Then:`,
    kept: (path: string) => `The phone's own backup is kept as ${path}.`,
    after: [
      "Open WhatsApp, agree to the terms, and verify the same number.",
      "When WhatsApp finds the backup, tap Restore and type the 64-digit key.",
      "Wait for it to finish, then look through the chats.",
    ] as ReactNode[],
    manualTitle: "Without USB debugging",
    manual: "Copy the contents of this folder:",
    manualInto: "into this folder on the phone with USB file transfer, after renaming the phone's own Databases/msgstore.db.crypt15 so it's kept:",
  },
  restore: {
    title: "Restore onto the iPhone",
    lead: "Puts the new backup onto the iPhone over the cable, as Finder's Restore Backup does.",
    needWrite: "Write the new backup first.",
    goWrite: "Go to Write",
    warnTitle: "This replaces everything on the iPhone",
    warnBody: (date: string) =>
      `The iPhone goes back to how it was at its backup of ${date}, plus the converted chats. Anything that reached it after that (messages, photos, app data) is gone afterwards.`,
    beforeTitle: "Before you start",
    before: [
      "In WhatsApp on the iPhone, back up each account's chats to iCloud (Settings → Chats → Chat Backup → Back Up Now). That's the way back if anything goes wrong.",
      "Keep the iPhone in airplane mode from the backup until the restore is done, or make a new backup and go through Convert again.",
      "Turn off Find My. If Stolen Device Protection is on, iOS asks for that first: Settings → Face ID & Passcode → Stolen Device Protection → off (away from a familiar place, iOS makes you wait an hour). Then Settings → your name → Find My → Find My iPhone → off.",
      "Connect the iPhone with a cable, unlock it, and keep it unlocked. Close Finder's window for it.",
    ] as ReactNode[],
    phoneTitle: "The iPhone",
    looking: "Looking for the iPhone…",
    noPhone: "The iPhone this backup is from isn't connected",
    noPhoneBody: (others: number) =>
      others
        ? `${others} other iPhone${others > 1 ? "s are" : " is"} connected, but not this backup's. Connect the right one and look again.`
        : "Connect it with a cable, unlock it, and look again.",
    phoneLine: (ios: string) => `iOS ${ios}, connected by cable`,
    matches: "The new backup is from this iPhone",
    trusted: "This computer is trusted",
    notTrusted: "Not trusted yet: unlock the iPhone, tap Trust, and look again",
    findMyOff: "Find My is off",
    findMyOn: "Find My is on: turn it off (Stolen Device Protection first, if it's on), then look again",
    findMyUnknown: "Find My: can't tell. Unlock the iPhone and look again",
    lookAgain: "Look again",
    confirmTitle: "Confirm",
    typeName: (name: string) => `Type ${name} to confirm`,
    working: (percent: number) => `Restoring… ${Math.round(percent)}%`,
    keepConnected: "Keep the iPhone connected and unlocked until it restarts.",
    run: "Restore the iPhone",
    doneTitle: "Restored",
    doneLine: (at: string) => `Restored ${at}. Then:`,
    after: [
      "The iPhone restarts and finishes restoring. Keep it connected until the lock screen shows, then unlock it.",
      "Apps reinstall from the App Store in the background: wait for WhatsApp.",
      "Open WhatsApp, switch to the account the chats went to, and look through them. If it asks to verify the number, do. If it offers to restore chat history from iCloud, skip it: that would replace the converted chats.",
      "Turn Find My back on, then Stolen Device Protection.",
    ] as ReactNode[],
  },
  results: {
    title: "Results",
    lead: "This summary holds counts, versions and file locations: no messages, names or phone numbers. Send it on if something needs looking into.",
    summaryLabel: "Summary",
    summaryLanguage: null as string | null,
    copy: "Copy summary",
    copied: "Copied",
    nextTitle: "What happens next",
    next: "Once the iPhone has restarted, open WhatsApp and check the account the chats went to. To move another Android account, check its backup on the Android step and go through the steps again.",
    cleanTitle: "Cleaning up",
    clean: (home: string): ReactNode => (
      <>
        Decrypted copies are in <Code>{home}</Code>. Delete that folder whenever you like; the summary above doesn't
        need it.
      </>
    ),
    startOver: "Start over",
    confirmReset: "Forget all progress? Decrypted copies stay on disk until you delete them.",
  },
}

export type Messages = typeof en
