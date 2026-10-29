// The page's words, in English and Simplified Chinese. English is the shape:
// the Chinese must fill every key, or the build fails. Menu names follow
// what WhatsApp, Android and Apple show in each language.
//
// Not translated here: messages the server writes (errors, the summary to
// send on), which are English everywhere.

import { createContext, useContext, type ReactNode } from "react"

import { Code } from "@/components/code"

export type Lang = "en" | "zh"
export const LANGS: { id: Lang; name: string }[] = [
  { id: "en", name: "English" },
  { id: "zh", name: "中文（简体）" },
]

type Platform = "darwin" | "win32" | "other"

const en = {
  header: {
    tagline: "Stays on this computer · writes to the iPhone only when you restore",
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
    done: "Results",
  },
  stepOf: (n: number, total: number) => `Step ${n} of ${total}`,
  stepLabel: (n: number, title: string, done: boolean) => `Step ${n}: ${title}${done ? " (done)" : ""}`,
  stepSkipped: "not needed",
  nav: { back: "Back", continue: "Continue", start: "Start" },
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
    "chats matched": "chats already on the iPhone",
    "chats created": "chats added",
    "media placed": "media files placed",
    "media missing": "media files not found",
  } as Record<string, string>,
  start: {
    title: "Move WhatsApp chats from Android to iPhone",
    lead: "This wizard checks both phones' backups so the transfer can be built for your exact setup. It only reads: nothing is written to either phone or to any backup.",
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
    skipped: (n: string) =>
      `${n} events the iPhone keeps differently (system notices, calls, polls and the like) are left out.`,
    notYet: (what: string, n: string) => `${what}: ${n}, not carried over yet (the messages themselves are).`,
  },
  preview: {
    title: "What the account will have",
    loading: "Reading the result…",
    totals: (fresh: string, joined: string, unchanged: string, messages: string) =>
      `${fresh} new chat${fresh === "1" ? "" : "s"} and ${joined} joined with chats already there (${messages} message${messages === "1" ? "" : "s"} from Android); ${unchanged} iPhone chat${unchanged === "1" ? "" : "s"} untouched.`,
    fromAndroid: "From Android",
    all: "All chats",
    search: "Search by name or number",
    noChats: "No chats match.",
    group: "Group",
    change: { new: "New", joined: "Joined", unchanged: "iPhone only" },
    chatLine: (android: string, total: string, first: string, last: string) =>
      `${android} of ${total} messages from Android · ${first} to ${last}`,
    showAll: (n: string) => `Show all ${n}`,
    newest: (n: string) => `newest messages of ${n}; outlined ones come from Android`,
    androidMark: "Android",
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
      "Turn off Find My: Settings → your name → Find My → Find My iPhone.",
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
    findMyOn: "Find My is on: turn it off, then look again",
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
      "Turn Find My back on.",
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

const zh: Messages = {
  header: {
    tagline: "只在这台电脑上运行 · 只有在你恢复时才写入 iPhone",
    language: "语言",
    theme: "主题",
    light: "浅色",
    dark: "深色",
    system: "跟随系统",
  },
  steps: {
    start: "开始",
    android: "安卓",
    before: "iPhone",
    account: "账号",
    after: "对比",
    convert: "转换",
    write: "写入",
    restore: "恢复",
    done: "结果",
  },
  stepOf: (n, total) => `第 ${n} 步，共 ${total} 步`,
  stepLabel: (n, title, done) => `第 ${n} 步：${title}${done ? "（已完成）" : ""}`,
  stepSkipped: "无需此步",
  nav: { back: "上一步", continue: "继续", start: "开始" },
  common: {
    loading: "加载中…",
    openWithLink: "请用 `whatferry ui` 打印的链接打开向导。",
    cantReach: (m) => `无法连接 whatferry：${m}。\`whatferry ui\` 还在运行吗？`,
    failed: "出错了",
    checked: "已检查",
    searchAgain: "重新搜索",
    messagesRange: (a, b) => (
      <>
        消息时间：<strong>{a}</strong> 至 <strong>{b}</strong>。
      </>
    ),
    noMessages: "还没有消息。",
  },
  counts: {
    chats: "聊天",
    messages: "消息",
    media: "媒体",
    "quoted replies": "引用回复",
    "reactions and other add-ons": "回应及其他附加内容",
    "contact cards": "联系人名片",
    locations: "位置",
    calls: "通话",
    "contacts and groups (jid)": "联系人和群组（jid）",
    "group members": "群成员",
    "group info": "群信息",
    "message info (receipts)": "消息信息（回执）",
    "profile push names": "资料名称",
    "files added": "新增文件",
    "files changed": "更改的文件",
    "files removed": "删除的文件",
    "chats matched": "iPhone 上已有的聊天",
    "chats created": "新增的聊天",
    "media placed": "已放入的媒体文件",
    "media missing": "未找到的媒体文件",
  },
  start: {
    title: "把 WhatsApp 聊天从安卓手机转移到 iPhone",
    lead: "这个向导会检查两部手机的备份，以便根据你的具体情况来实现转移。它只读取数据：不会向任何一部手机或任何备份写入内容。",
    needTitle: "你需要",
    needs: [
      "安卓手机，装有 WhatsApp 和你要转移的聊天。",
      "iPhone，已为它自己的号码设置好 WhatsApp。",
      "一根把 iPhone 连接到这台电脑的数据线。",
      "大约一小时，大部分时间在等备份完成。你可以关掉页面稍后再回来：进度会保存。",
    ],
    happensTitle: "接下来会做什么",
    happens: [
      "在安卓手机上创建加密的 WhatsApp 备份，并把文件传到这台电脑。",
      "备份 iPhone，让向导了解 WhatsApp 如何存储你当前的账号。",
      "在 iPhone 的 WhatsApp 中把安卓手机的号码添加为第二个账号。",
      "再次备份 iPhone。比较两次备份，就能准确看出新账号的聊天会存放在哪里。",
    ],
    privateTitle: "哪些内容保持私密",
    privateLead: "任何内容都不会离开这台电脑。",
    private: (home) => [
      "页面只与这台电脑上的 whatferry 通信，不会上传任何内容。",
      "密钥和密码只使用一次，从不保存。",
      <>
        解密后的副本保存在 <Code>{home}</Code>，只有你能读取。用完后可以删除。
      </>,
    ],
  },
  android: {
    title: "安卓备份",
    lead: "WhatsApp 的加密备份配合你记下的 64 位密钥，无需 root 手机即可在这里读取。",
    makeTitle: "在安卓手机上创建备份",
    make: [
      "打开 WhatsApp → 设置 → 聊天 → 聊天备份 → 端对端加密备份 → 开启。",
      "选择“改用 64 位加密密钥”，然后生成密钥。请把它抄下来或截图：WhatsApp 无法再次显示它。",
      "回到“聊天备份”，点按“备份”。即使关闭了 Google 云端硬盘备份，手机上也会保存一个文件。",
    ],
    multiTitle: "手机上有不止一个 WhatsApp 账号？",
    multiBody: "每个账号都有自己的备份和自己的密钥。先切换到要转移的账号（点按头像 → 切换账号），再完成上面的步骤；每个要转移的账号都重复一遍。",
    bringTitle: "把文件传到这台电脑",
    bringLead: "以下任何一种方式都可以，选最方便的。",
    tabs: { share: "从手机分享", cable: "USB 文件传输", adb: "通过 USB 调试复制" },
    share: [
      <>
        打开手机的“文件”应用（Google 的“Files”，或三星的“我的文件”），进入{" "}
        <Code>Android/media/com.whatsapp/WhatsApp</Code>。有些文件应用会隐藏 <Code>Android</Code> 文件夹，Google 的
        Files 会显示它。
      </>,
      <>
        打开 <Code>Databases</Code>；如果有多个账号，则打开 <Code>accounts</Code> → 账号编号 → <Code>Databases</Code>。
      </>,
      <>
        长按 <Code>msgstore.db.crypt15</Code>（不带日期的那个），点按“分享”。
      </>,
      "用你手头的任何方式发到这台电脑：LocalSend（免费，手机和电脑在同一个 Wi-Fi 下，不经过互联网）、快速分享（Windows）、Google 云端硬盘，或者发邮件、发消息给自己。",
      "把它保存到“下载”文件夹，然后点击下面的“重新搜索”。",
    ],
    cable: (platform) => [
      "用 USB 数据线把手机连接到这台电脑，并解锁手机。",
      "在手机上点按“正在通过 USB 为此设备充电”通知，选择“文件传输”。",
      {
        darwin: "Mac 无法直接打开安卓手机：请安装 OpenMTP（免费，openmtp.ganeshrvel.com），并在其中打开手机。",
        win32: "打开文件资源管理器：手机会出现在“此电脑”下。",
        other: "你的文件管理器会在侧边栏中显示手机。",
      }[platform],
      "把下面文件夹中的 msgstore.db.crypt15 复制到“下载”文件夹，然后点击下面的“重新搜索”。",
    ],
    foldersTitle: "WhatsApp 在手机上存放备份的位置",
    folders: ["一个账号", "多个账号", "WhatsApp Business", "Android 10 或更早版本"],
    foldersNote: (
      <>
        有多个账号时，每个 <Code>accounts/&lt;编号&gt;</Code> 文件夹对应一个账号：选择刚点按“备份”后
        msgstore.db.crypt15 最新的那个。以 .crypt14 结尾的文件、带日期的文件和“increment”文件都无法使用。
      </>
    ),
    chooseTitle: "选择文件",
    searching: "正在搜索…",
    noneFound: "还没有找到 WhatsApp 备份。",
    chooseFile: "选择文件…",
    copyingFile: (name) => `正在复制 ${name}…`,
    searchHint: (folders) => <>“重新搜索”会在 {folders} 中查找 WhatsApp 备份。在别的位置？请使用“选择文件”。</>,
    listAnd: " 和 ",
    listSep: "、",
    keyTitle: "输入密钥",
    keyLabel: "64 位密钥",
    keyPlaceholder: "64 个字符，可以带空格",
    showKey: "显示密钥",
    hideKey: "隐藏密钥",
    keyHint: "只用于解密一次，随后即被丢弃。如果你选择的是已解密的 msgstore.db，则不需要。",
    decrypting: "正在解密并检查备份…",
    decrypt: "解密并检查",
    checkAgain: "重新检查",
    resultLine: (version, db, checked) => `WhatsApp ${version} · 数据库版本 ${db} · 检查于 ${checked}`,
    legacy: "这个备份使用 WhatsApp 的旧格式。请在手机上更新 WhatsApp 后重新备份。",
    jidTitle: "按类型统计的联系人标识",
    jidHead: ["服务器", "数量"],
    decryptedCopy: "解密后的副本：",
    accountsTitle: "安卓账号",
    accountsLead: "每个账号单独转移。要添加另一个账号，请在下面选择它的备份文件并解密；在这里切换要处理的账号。",
    accountRow: (ends, messages) => `号码以 ${ends ?? "?"} 结尾 · ${messages} 条消息`,
    accountProgress: (destination, secondDone) =>
      [destination ? `转移到：${destination}` : "还没有选择转移位置", secondDone ? "已检查第二次备份" : null]
        .filter(Boolean).join(" · "),
    destinationNames: { setup: "设置 WhatsApp", second: "第二个账号", existing: "现有账号" },
    workingOn: "正在处理这个账号",
    switchTo: "切换到这个账号",
    movingAccount: (ends) => `安卓账号，号码以 ${ends ?? "?"} 结尾`,
  },
  phone: {
    intro: (folder) => (
      <>
        把手机连接到这台电脑，whatferry 会直接把备份复制到 <Code>{folder}</Code>。需要在手机上开启 USB 调试，并在这台电脑上安装
        adb；用完后可以再关闭调试。
      </>
    ),
    looking: "正在查找 adb 和已连接的手机…",
    noAdbTitle: "这台电脑上没有安装 adb",
    noAdbIntro: "adb 是 Google 提供的免费工具，用于通过 USB 与安卓手机通信。",
    install: {
      darwin: ["使用 Homebrew：brew install --cask android-platform-tools", "或者从 Google 下载 platform-tools（见下方）并解压。"],
      win32: ["在终端中运行：winget install Google.PlatformTools", "或者从 Google 下载 platform-tools（见下方）并解压。"],
      other: ["Debian 或 Ubuntu：sudo apt install adb · Fedora：sudo dnf install android-tools", "或者从 Google 下载 platform-tools（见下方）并解压。"],
    },
    download: (
      <>
        Google 下载地址：<Code>developer.android.com/tools/releases/platform-tools</Code>。如果 adb 在 whatferry
        找不到的位置，请用 <Code>WHATFERRY_ADB=/path/to/adb</Code> 启动它。
      </>
    ),
    debugTitle: "开启 USB 调试",
    debug: [
      "在手机上打开“设置”→“关于手机”，连续点按“版本号”七次。如有提示请输入 PIN 码，随后会显示“您现在处于开发者模式”。（三星：设置 → 关于手机 → 软件信息 → 编译编号。）",
      "返回“设置”→“系统”→“开发者选项”，开启“USB 调试”。",
      "用 USB 数据线把手机连接到这台电脑，并解锁手机。",
      "在“允许 USB 调试吗？”中点按“允许”。勾选“一律允许使用这台计算机进行调试”以后就不用再确认。",
      "点击下面的“查找手机”。",
    ],
    debugOff: "用完后：开发者选项 → 关闭“USB 调试”。",
    notReady: (model) => `${model} 尚未就绪`,
    advice: {
      unauthorized: "请解锁手机，并在“允许 USB 调试吗？”中点按“允许”。",
      offline: "手机没有响应：请拔下后重新连接，并解锁手机。",
      "no permissions": "这台电脑没有与手机通信的权限（在 Linux 上，请为安卓添加 udev 规则）。",
      authorizing: "正在等待你在手机上点按“允许”。",
    },
    otherState: (state) => `adb 显示“${state}”。`,
    phone: "安卓手机",
    connected: "已连接",
    account: (app, account) => (account ? `${app} · 账号 ${account}` : app),
    noBackups: "这部手机上还没有 WhatsApp 备份。请先创建一个（第 1 步），然后再点击“查找手机”。",
    noUsable: "还没有可用的备份：请开启 64 位加密备份并点按“备份”（第 1 步），然后再点击“查找手机”。",
    otherFiles: (n) => `另有 ${n} 个无法使用的文件`,
    notes: {
      rooted: "旧的加密方式：它的密钥只存在于已 root 的手机上。请开启 64 位加密备份并重新备份，以获得 .crypt15 文件。",
      increment: "这是部分（增量）备份；请使用完整的 msgstore 文件。",
      other: "这不是 WhatsApp 聊天备份。",
    },
    copy: "复制",
    copying: "正在复制…",
    copiedTitle: (name) => `已复制 ${name}`,
    copiedBody: "已在下面的第 3 步中选中。",
    findPhone: "查找手机",
  },
  backup: {
    title: { before: "iPhone 备份", after: "第二次 iPhone 备份" },
    lead: {
      before: "备份可以显示 iPhone 上的 WhatsApp 目前如何存储数据。向导只读取它，从不修改。",
      after: "添加第二个账号后，新的备份会显示新账号创建了哪些文件。安卓的聊天就会放到那里。",
    },
    needFirst: "请先检查第一次 iPhone 备份。",
    goFirst: "前往第一次备份",
    makeTitle: { before: "备份 iPhone", after: "再次备份 iPhone" },
    make: {
      darwin: [
        "用数据线把 iPhone 连接到这台 Mac 并解锁。如有提示，请点按“信任”。",
        "打开“访达”，在边栏中选择这部 iPhone。",
        "在“备份”下，选择“将 iPhone 上的所有数据备份到这台 Mac”。",
        "勾选“加密本地备份”，并设置一个你记得住的密码。稍后要在这里输入它。",
        "点击“立即备份”，等待完成。",
      ],
      win32: [
        "用数据线把 iPhone 连接到这台电脑并解锁。如有提示，请点按“信任”。",
        "打开“Apple 设备”应用（或 iTunes），选择这部 iPhone。",
        "在“备份”下，选择“将 iPhone 上的所有数据备份到这台电脑”。",
        "勾选“加密本地备份”，并设置一个你记得住的密码。稍后要在这里输入它。",
        "点击“立即备份”，等待完成。",
      ],
      other: [
        "安装 libimobiledevice，用数据线连接 iPhone，解锁并点按“信任”。",
        "开启一次加密：idevicebackup2 encryption on",
        "创建备份：idevicebackup2 backup --full <文件夹>",
        "用 WHATFERRY_BACKUP_ROOT=<文件夹> 启动向导，让它能找到备份。",
      ],
    },
    samePassphrase: "请使用与之前相同的密码。新备份会替换同一文件夹中的旧备份；向导已经保留了第一次备份中需要的内容。",
    chooseTitle: "选择备份",
    looking: "正在查找备份…",
    noneTitle: "还没有找到备份",
    lookedIn: (folders) => `已查找：${folders}。`,
    noRoot: "这个系统没有标准的备份文件夹：请设置 WHATFERRY_BACKUP_ROOT。",
    encrypted: "已加密",
    notEncrypted: "未加密",
    iphone: "iPhone",
    deviceLine: (model, ios, date) => `${model} · iOS ${ios} · 备份于 ${date}`,
    notEncryptedTitle: "这个备份没有加密",
    notEncryptedBody: "用来检查没有问题，但转移时需要加密的备份：请勾选“加密本地备份”后重新备份。",
    passLabel: "备份密码",
    passHint: "就是你勾选“加密本地备份”时设置的密码。只使用一次，从不保存。",
    unlocking: "正在解锁备份。这需要一两分钟：慢是因为加密在起作用。",
    reading: "正在读取备份…",
    check: { before: "检查这个备份", after: "检查并比较" },
    checkAgain: "重新检查",
    resultLine: (model, ios, backed, checked) => `${model} · iOS ${ios} · 备份于 ${backed} · 检查于 ${checked}`,
    noWhatsapp: "这个备份中没有 WhatsApp 数据。这部 iPhone 上安装了 WhatsApp 吗？",
    chatsIn: (path) => (
      <>
        聊天位于 <code className="font-mono text-xs">{path}</code>
      </>
    ),
    messagesRange: (a, b) => `消息时间：${a} 至 ${b}`,
    manyStores: (n) => `${n} 个聊天数据库：可能每个账号一个。`,
    areasTitle: "WhatsApp 的存储区域",
    areasHead: ["区域", "文件", "大小"],
    savedList: "已保存这个备份的文件列表，用于与下一次备份比较。",
    diffTitle: "添加账号带来的变化",
    foundOne: "找到了新账号的聊天数据库",
    foundMany: (n) => `找到了 ${n} 个新的聊天数据库`,
    whereGo: "安卓的聊天就会放到这里。",
    noneNewTitle: "没有出现新的聊天数据库",
    noneNewBody: "第二个账号可能与现有账号共用一个数据库，或者备份时 WhatsApp 还没有完成设置。完整的变化列表见下方。",
    diffHead: ["位置", "新增", "更改", "删除"],
    filesAdded: "新增的文件",
    filesChanged: "更改的文件",
  },
  destination: {
    title: "安卓的聊天应该放到哪里？",
    lead: "选择这部 iPhone 上由哪个 WhatsApp 账号接收它们。建议根据备份中看到的情况给出。",
    suggested: "建议",
    options: {
      setup: {
        title: "用安卓手机的号码在这部 iPhone 上设置 WhatsApp",
        body: "这部 iPhone 上还没有设置 WhatsApp：安卓手机的号码将成为它唯一的账号。",
      },
      second: {
        title: "把安卓手机的号码添加为第二个账号",
        body: "iPhone 保留现有账号；安卓的聊天放进它旁边一个新的空账号。",
      },
      existing: {
        title: "这里已有账号在使用安卓手机的号码",
        body: "安卓的聊天放进那个账号。如果它已经有聊天，两份记录会被合并。",
      },
    },
    reasons: {
      noWhatsapp: "这个备份中没有 WhatsApp 数据。",
      matches: (ends) => `这里有一个账号的号码以 ${ends} 结尾，与安卓备份的号码相同（只知道最后两位，请确认确实是同一个号码）。`,
      different: (ends, accounts) => `安卓的号码以 ${ends} 结尾；这部 iPhone 上账号的号码以 ${accounts} 结尾。`,
      unknown: "安卓备份没有记录它的号码，所以向导无法比较。",
      stale: "这次 iPhone 检查使用的是较旧的账号读取方式，可能会把聊天误认为账号。请点击上方的“重新检查”来比较号码。",
      secondStarted: (ends) =>
        `安卓的号码（以 ${ends} 结尾）已经在这里被设置为第二个账号，但它还没有聊天：登录可能在输入验证码之前就停止了。请在 iPhone 上完成登录，然后进行第二次备份。`,
      iphoneUnknown: (ends) => `安卓的号码以 ${ends} 结尾，但无法从这个备份中读取 iPhone 账号的号码。`,
    },
    full: "这部 iPhone 上可能已经有第二个 WhatsApp 账号：备份中有一个它的文件夹。如果是这样，WhatsApp 可能不允许第三个，你可能需要先移除一个。",
    merge: (n) => `那个账号在这部 iPhone 上已经有 ${n} 条消息。合并会保留两份记录，但这是最难做对的情况。`,
    notMatching: (ends, numbers) =>
      `这里没有号码以 ${ends} 结尾的账号。选择这一项，安卓的聊天会放进一个号码不同的账号（以 ${numbers} 结尾），并显示在那个号码下。`,
    cantConfirm: "向导无法确认这里有账号在使用安卓手机的号码：选择这一项之前，请先在 iPhone 上的 WhatsApp 中确认。",
    replaceExisting: (numbers) =>
      `这部 iPhone 上已经设置了 WhatsApp${numbers ? `（号码以 ${numbers} 结尾）` : ""}。用安卓手机的号码重新设置会让那个账号退出登录；如要保留它，请改为添加第二个账号。`,
    accountsTitle: "这部 iPhone 上的 WhatsApp 账号",
    account: (numberEnds, country, main, hasChats) =>
      `号码以 ${numberEnds ?? "?"} 结尾${country ? `（${country}）` : ""} · ${main ? "主账号" : "第二个账号"}${hasChats ? "" : " · 此备份中没有聊天"}`,
    secondNoChats: "那个账号的聊天不在 iPhone 备份中：要么它还没有聊天，要么 WhatsApp 不把第二个账号的聊天放进备份。转移必须绕过这一点，所以这是接下来要弄清楚的事。",
    folders: (n) => `备份中还有 ${n} 个 WhatsApp 为其他账号保留的文件夹，可能是第二个账号；无法读取它的号码。`,
    chooseFirst: "请先检查 iPhone 备份，然后选择聊天放到哪里。",
  },
  account: {
    setup: {
      title: "用安卓手机的号码设置 WhatsApp",
      lead: "WhatsApp 会为安卓手机的号码创建数据库、文件夹和密钥。下一次备份会显示它们的位置。",
      sectionTitle: "在 iPhone 上设置 WhatsApp",
      steps: [
        "如果还没有安装，请从 App Store 安装 WhatsApp。",
        "打开它并注册安卓手机的号码，输入 WhatsApp 发送的验证码。安卓手机上的 WhatsApp 会退出登录：这是正常的，你的备份文件已经安全地保存在这台电脑上。",
        "如果 WhatsApp 提出恢复聊天，请跳过。账号应该从空白开始。",
      ],
    },
    existing: {
      title: "iPhone 上无需添加任何内容",
      lead: "已经在使用安卓手机号码的账号会接收这些聊天。不需要第二次备份：请继续查看结果。",
    },
    none: "请先选择聊天放到哪里：在“iPhone 备份”步骤的最后。",
    goChoose: "选择聊天放到哪里",
    notNeeded: "此选择无需这一步",
    skipNote: "接收聊天的账号已经存在，所以没有新的内容需要查找。请继续查看结果。",
    title: "在 iPhone 上添加安卓手机的号码",
    lead: "WhatsApp 会自己设置第二个账号：它自己的空数据库、文件夹和密钥。之后只有这个新账号会被填入安卓的聊天，你现在的账号不会受到影响。",
    addTitle: "在 iPhone 上添加账号",
    steps: [
      "在 iPhone 上打开 WhatsApp → 设置，选择“添加账号”（在顶部你的名字旁边）。",
      "注册安卓手机的号码，并输入 WhatsApp 发送的验证码。安卓手机上的 WhatsApp 会退出登录：这是正常的，你的备份文件已经安全地保存在这台电脑上。",
      "如果 WhatsApp 提出为新账号恢复聊天，请跳过。新账号应该从空白开始。",
    ],
    keepAndroid: "在转移完成之前，请保留安卓手机上的 WhatsApp。万一出了问题，你还可以在那里重新登录，聊天仍然都在。",
  },
  convert: {
    title: "转换聊天",
    lead: "把安卓账号的聊天记录合并到 iPhone 账号聊天数据库的副本中。两部手机和备份此时都不会有任何改动：写入之前先在下方查看结果，如果不对，换个选择再转换一次。",
    needBackups: "请先检查安卓备份和 iPhone 备份。",
    goAndroid: "前往安卓备份",
    goIphone: "前往 iPhone 备份",
    targetTitle: "哪个 iPhone 账号接收这些聊天",
    fromBackup: (second, date) => `来自${second ? "第二次" : "第一次"} iPhone 备份，检查于 ${date}。`,
    mainAccount: (ends) => `主账号${ends ? `，号码尾号 ${ends}` : ""}`,
    otherAccount: (ends) => `添加的账号${ends ? `，号码尾号 ${ends}` : ""}`,
    suggested: "推荐",
    hasMessages: (n) => `目前有 ${n} 条消息`,
    mergeNote: (n) => `这个账号已有 ${n} 条消息。安卓聊天会加在它们旁边；与同一个人或群组的聊天会合并在一起。`,
    mediaTitle: "照片、视频和语音消息",
    mediaLead: "复制到这台电脑上的安卓 WhatsApp Media 文件夹。找到的每个文件夹都会与安卓聊天中最新的文件逐一核对。",
    mediaFound: (found, sampled) =>
      sampled ? `包含聊天中最新 ${sampled} 个文件里的 ${found} 个` : "聊天中没有媒体文件",
    mediaOther: "其他文件夹",
    mediaPlaceholder: "WhatsApp/Media 副本的路径",
    mediaNone: "不含媒体",
    mediaNoneNote: "消息会保留说明文字；照片和视频本身不会带过去。",
    working: "正在转换……需要一两分钟。",
    run: "转换",
    again: "重新转换",
    doneTitle: (converted, total) => `已转换 ${total} 条消息中的 ${converted} 条`,
    doneLine: (at) => `转换于 ${at}。`,
    checksClean: "合并后的数据库通过了所有一致性检查。",
    checksFailed: "合并后的数据库未通过一致性检查",
    skipped: (n) => `有 ${n} 个 iPhone 以不同方式保存的事件（系统通知、通话、投票等）未包含在内。`,
    notYet: (what, n) => `${what}：${n} 条，暂未转移（消息本身已转移）。`,
  },
  preview: {
    title: "该账号将包含的内容",
    loading: "正在读取结果……",
    totals: (fresh, joined, unchanged, messages) =>
      `${fresh} 个新聊天，${joined} 个与已有聊天合并（来自安卓的消息 ${messages} 条）；${unchanged} 个 iPhone 聊天保持不变。`,
    fromAndroid: "来自安卓",
    all: "全部聊天",
    search: "按名字或号码搜索",
    noChats: "没有匹配的聊天。",
    group: "群组",
    change: { new: "新增", joined: "合并", unchanged: "仅 iPhone" },
    chatLine: (android, total, first, last) => `${total} 条消息中 ${android} 条来自安卓 · ${first} 至 ${last}`,
    showAll: (n) => `显示全部 ${n} 个`,
    newest: (n) => `共 ${n} 条中的最新消息；带边框的来自安卓`,
    androidMark: "安卓",
    kinds: {
      image: "照片",
      video: "视频",
      audio: "语音消息或音频",
      contact: "联系人名片",
      location: "位置",
      document: "文档",
      gif: "GIF",
      sticker: "贴纸",
      deleted: "此消息已删除",
      link: "链接",
      system: "聊天事件",
      other: "其他消息",
    },
  },
  write: {
    title: "写入新备份",
    lead: "复制 iPhone 备份，并把转换后的聊天放进副本，按 iOS 的方式加密。写入的每个文件都会读回并核对。",
    needConvert: "请先转换聊天。",
    goConvert: "前往转换",
    fromTitle: "作为起点的备份",
    from: (date) => `${date} 的 iPhone 备份，聊天就是转换到这个备份里的：`,
    untouched: "那个备份保持原样；新备份放在 whatferry 自己的文件夹中。",
    previewFirst: "写入的内容就是预览中显示的转换结果。",
    openPreview: "查看预览",
    passTitle: "密码",
    noPass: "这个备份没有加密：不需要密码。",
    skipLabel: "即使转换后备份有变化也写入",
    skipNote: "通常会被拒绝：备份必须是聊天转换进去的那一个。勾选后，转换之后该账号在 iPhone 上收到的内容会在恢复时丢失。",
    changedTitle: "转换之后这个备份有变化",
    changedBody: "在对应步骤中重新检查最新的 iPhone 备份，然后再转换一次。这样能保留该账号现在的所有内容。",
    working: "正在写入……大型备份需要几分钟。",
    run: "写入新备份",
    again: "重新写入",
    doneTitle: "新备份已写入并核对",
    unchecked: "未核对来源",
    doneLine: (at) => `写入于 ${at}。`,
    added: (files, bytes, verified) => `新增 ${files} 个文件（${bytes}）；${verified} 个文件已读回并核对。`,
  },
  restore: {
    title: "恢复到 iPhone",
    lead: "通过数据线把新备份恢复到 iPhone，与访达的“恢复备份”相同。",
    needWrite: "请先写入新备份。",
    goWrite: "前往写入",
    warnTitle: "这会替换 iPhone 上的所有内容",
    warnBody: (date) =>
      `iPhone 会回到 ${date} 备份时的状态，再加上转换后的聊天。在那之后收到的内容（消息、照片、应用数据）都会消失。`,
    beforeTitle: "开始之前",
    before: [
      "在 iPhone 的 WhatsApp 中，把每个账号的聊天备份到 iCloud（设置 → 聊天 → 聊天备份 → 立即备份）。出问题时可以靠它恢复。",
      "从备份时起到恢复完成，让 iPhone 保持飞行模式；或者重新备份，再做一次转换。",
      "关闭“查找”：设置 → 你的名字 → 查找 → 查找我的 iPhone。",
      "用数据线连接 iPhone，解锁并保持解锁。关闭访达中它的窗口。",
    ],
    phoneTitle: "iPhone",
    looking: "正在查找 iPhone……",
    noPhone: "没有连接这个备份所属的 iPhone",
    noPhoneBody: (others) =>
      others ? `已连接 ${others} 部其他 iPhone，但不是这个备份的那一部。请连接正确的 iPhone 再查找。` : "用数据线连接并解锁，然后再查找。",
    phoneLine: (ios) => `iOS ${ios}，已通过数据线连接`,
    matches: "新备份来自这部 iPhone",
    trusted: "这台电脑已受信任",
    notTrusted: "尚未受信任：解锁 iPhone，轻点“信任”，然后再查找",
    findMyOff: "“查找”已关闭",
    findMyOn: "“查找”已开启：关闭后再查找",
    findMyUnknown: "“查找”：无法判断。解锁 iPhone 后再查找",
    lookAgain: "再次查找",
    confirmTitle: "确认",
    typeName: (name) => `输入 ${name} 以确认`,
    working: (percent) => `正在恢复……${Math.round(percent)}%`,
    keepConnected: "在 iPhone 重新启动之前，保持连接和解锁。",
    run: "恢复 iPhone",
    doneTitle: "已恢复",
    doneLine: (at) => `恢复于 ${at}。接下来：`,
    after: [
      "iPhone 会重新启动并完成恢复。在出现锁定屏幕之前保持连接，然后解锁。",
      "应用会在后台从 App Store 重新安装：等待 WhatsApp 安装完成。",
      "打开 WhatsApp，切换到接收聊天的账号并查看。如果要求验证号码，请照做。如果提示从 iCloud 恢复聊天记录，请跳过：那会替换转换后的聊天。",
      "重新打开“查找”。",
    ],
  },
  results: {
    title: "结果",
    lead: "这份摘要只包含数量、版本和文件位置：没有消息、名字或电话号码。如果需要排查问题，可以把它发出去。",
    summaryLabel: "摘要",
    summaryLanguage: "摘要是英文的，便于发给开发者。",
    copy: "复制摘要",
    copied: "已复制",
    nextTitle: "接下来",
    next: "iPhone 重新启动后，打开 WhatsApp 查看接收聊天的账号。要转移另一个安卓账号，请在安卓步骤中检查它的备份，再走一遍这些步骤。",
    cleanTitle: "清理",
    clean: (home) => (
      <>
        解密后的副本位于 <Code>{home}</Code>。你随时可以删除这个文件夹；上面的摘要不需要它。
      </>
    ),
    startOver: "重新开始",
    confirmReset: "要清除所有进度吗？解密后的副本会保留在磁盘上，直到你删除它们。",
  },
}

export const MESSAGES: Record<Lang, Messages> = { en, zh }

export function locale(lang: Lang): string {
  if (lang === "zh") return "zh-CN"
  return navigator.language.toLowerCase().startsWith("en") ? navigator.language : "en"
}

export const I18nContext = createContext<{ lang: Lang; t: Messages; setLang: (l: Lang) => void }>({
  lang: "en",
  t: en,
  setLang: () => {},
})

export function useI18n() {
  return useContext(I18nContext)
}

/** The language to start in: saved choice, else the browser's, else English. */
export function toLang(saved: string | undefined): Lang {
  if (saved === "en" || saved === "zh") return saved
  return navigator.languages.some((l) => l.toLowerCase().startsWith("zh")) &&
    !navigator.languages[0]?.toLowerCase().startsWith("en")
    ? "zh"
    : "en"
}
