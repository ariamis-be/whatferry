"use strict";

// whatferry's wizard. Talks only to the local server that served it, with the
// token from the link `whatferry ui` opened. Everything shown is built with
// textContent: nothing from a backup is ever parsed as HTML.

const TOKEN = new URLSearchParams(location.search).get("t") || "";

const STEPS = [
  { id: "start", title: "Before you start" },
  { id: "android", title: "Android backup" },
  { id: "before", title: "iPhone backup" },
  { id: "account", title: "Add the account" },
  { id: "after", title: "Second iPhone backup" },
  { id: "done", title: "Results" },
];

const CHECKLIST = [
  ["add-account", "On the iPhone, open WhatsApp → Settings and choose Add account (next to your name at the top)."],
  ["register-number", "Register the Android phone's number and enter the code WhatsApp sends. WhatsApp on the Android phone signs out: that's expected, and your backup file is already safe on this computer."],
  ["leave-empty", "If WhatsApp offers to restore chats for the new account, skip it. The new account should start empty."],
  ["new-backup", "Make a new encrypted backup of the iPhone, the same way as before."],
];

const BACKUP_STEPS = {
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
};

let overview = null;
let current = "start";
const ui = { android: {}, before: {}, after: {} };

// ---- Server ----

async function api(method, path, body) {
  const headers = { "X-Whatferry-Token": TOKEN };
  let payload;
  if (body instanceof Blob) {
    payload = body;
    headers["Content-Type"] = "application/octet-stream";
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  const extra = body instanceof Blob ? { "X-Filename": encodeURIComponent(body.name || "") } : {};
  const res = await fetch(path, { method, headers: { ...headers, ...extra }, body: payload });
  let data = {};
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) throw new Error(data.error || `request failed (${res.status})`);
  return data;
}

async function runJob(path, body) {
  const { job } = await api("POST", path, body);
  for (;;) {
    await new Promise((r) => setTimeout(r, 600));
    const status = await api("GET", `/api/jobs/${job}`);
    if (status.status === "done") return status.result;
    if (status.status === "error") throw new Error(status.error);
  }
}

async function refresh() {
  overview = await api("GET", "/api/overview");
}

function state() { return (overview && overview.state) || {}; }

// ---- DOM ----

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

const num = (n) => (typeof n === "number" ? n.toLocaleString() : "?");

function size(bytes) {
  if (typeof bytes !== "number") return "?";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return `${i ? bytes.toFixed(1) : bytes} ${units[i]}`;
}

function when(iso) {
  if (!iso) return "?";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function day(iso) {
  if (!iso) return "?";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

const notice = (kind, ...children) => h("div", { class: `alert ${kind}`, role: kind === "error" ? "alert" : null }, ...children);

function stats(counts) {
  const items = Object.entries(counts || {}).filter(([, n]) => n !== null && n !== undefined);
  return h("div", { class: "stats" }, items.map(([label, n]) => h("div", { class: "stat" }, h("b", { text: num(n) }), h("span", { text: label }))));
}

function table(headers, rows) {
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, headers.map((t) => h("th", { text: t })))),
    h("tbody", {}, rows.map((cells) => h("tr", {}, cells)))));
}

function busy(text) {
  return h("div", { class: "busy", role: "status" }, h("span", { class: "spinner", "aria-hidden": "true" }), text);
}

function nextButton(step, label = "Continue") {
  const i = STEPS.findIndex((s) => s.id === step);
  return h("button", { class: "btn primary", onclick: () => go(STEPS[i + 1].id), text: label });
}

// ---- Steps ----

function isDone(id) {
  const s = state();
  const list = s.checklist || {};
  switch (id) {
    case "start": return Boolean(s.android || s.before);
    case "android": return Boolean(s.android);
    case "before": return Boolean(s.before);
    case "account": return CHECKLIST.every(([key]) => list[key]);
    case "after": return Boolean(s.after);
    default: return false;
  }
}

function renderRail() {
  const list = document.getElementById("steps");
  list.replaceChildren(...STEPS.map((step, i) => h("li",
    { class: isDone(step.id) ? "done" : "", "aria-current": step.id === current ? "step" : null },
    // The label keeps the name when narrow screens hide the title.
    h("button", { onclick: () => go(step.id), "aria-label": isDone(step.id) ? `${step.title} (done)` : step.title },
      h("span", { class: "step-badge", "aria-hidden": "true", text: isDone(step.id) ? "✓" : String(i + 1) }),
      h("span", { class: "step-title", text: step.title })))));
}

function render() {
  renderRail();
  const main = document.getElementById("main");
  const view = { start: viewStart, android: viewAndroid, before: () => viewBackup("before"), account: viewAccount,
    after: () => viewBackup("after"), done: viewDone }[current];
  main.replaceChildren(...[].concat(view()));
}

async function go(step) {
  current = step;
  render();
  document.getElementById("main").focus();
  window.scrollTo(0, 0);
  try { await api("POST", "/api/step", { step }); } catch { /* progress only */ }
}

function viewStart() {
  return [
    h("h1", { text: "Move WhatsApp chats from Android to iPhone" }),
    h("p", { class: "lead", text: "This wizard checks both phones' backups so the transfer can be built for your exact setup. It only reads: nothing is written to either phone or to any backup." }),
    h("h2", { text: "You'll need" }),
    h("ul", { class: "plain" },
      h("li", { text: "The Android phone, with WhatsApp and the chats you want to move." }),
      h("li", { text: "The iPhone, with WhatsApp already set up for its own number." }),
      h("li", { text: "A cable to connect the iPhone to this computer." }),
      h("li", { text: "About an hour, mostly waiting for backups to finish. You can close this page and come back: progress is saved." })),
    h("h2", { text: "What happens" }),
    h("ol", { class: "instructions" },
      h("li", { text: "Make an encrypted WhatsApp backup on the Android phone and bring the file here." }),
      h("li", { text: "Back up the iPhone, so the wizard can see how WhatsApp stores your current account." }),
      h("li", { text: "Add the Android number to WhatsApp on the iPhone as a second account." }),
      h("li", { text: "Back up the iPhone again. Comparing the two backups shows exactly where the new account's chats will go." })),
    h("div", { class: "card" },
      h("h3", { text: "What stays private" }),
      h("ul", { class: "plain" },
        h("li", { text: "The page only talks to this computer. Nothing is uploaded anywhere." }),
        h("li", { text: "Keys and passphrases are used once and never saved." }),
        h("li", {}, "Decrypted copies are kept in ", h("code", { text: overview.home }), ", readable only by you. Delete it when you're done.")),
    ),
    h("div", { class: "actions" }, h("button", { class: "btn primary", onclick: () => go("android"), text: "Start" })),
  ];
}

function viewAndroid() {
  const s = state();
  const local = ui.android;
  const out = [
    h("h1", { text: "Android backup" }),
    h("p", { class: "lead", text: "WhatsApp's encrypted backup, with a 64-digit key you write down, can be read here without rooting the phone." }),
    h("h2", { text: "1. Make the backup on the Android phone" }),
    h("ol", { class: "instructions" },
      h("li", { text: "Open WhatsApp → Settings → Chats → Chat backup → End-to-end encrypted backup → Turn on." }),
      h("li", { text: "Choose “Use 64-digit encryption key instead”, then generate the key. Write it down: WhatsApp can't show it again." }),
      h("li", { text: "Back on Chat backup, tap Back up. This saves a file on the phone even if Google Drive backups are off." })),
    h("h2", { text: "2. Bring the file to this computer" }),
    h("p", {}, "In the phone's Files app, open ", h("code", { text: "Android/media/com.whatsapp/WhatsApp/Databases" }),
      " and share ", h("code", { text: "msgstore.db.crypt15" }), " (the one without a date) to this computer: LocalSend, Google Drive, or a USB cable in file-transfer mode all work."),
    h("h2", { text: "3. Choose the file" }),
  ];

  const files = local.files || [];
  if (!local.files && !local.looking) loadCandidates();
  const choices = h("div", { class: "choices", role: "radiogroup", "aria-label": "Backup file" },
    files.map((f) => h("label", { class: "choice" },
      h("input", { type: "radio", name: "android-file", value: f.path, checked: local.path === f.path,
        onchange: () => { local.path = f.path; render(); } }),
      h("span", {}, h("span", { class: "choice-title", text: f.name }),
        h("span", { class: "choice-meta", text: ` · ${size(f.size)} · ${when(f.modified)}` }),
        h("div", { class: "choice-meta", text: f.path })))));
  out.push(files.length ? choices : h("p", { class: "muted", text: local.files ? "No WhatsApp backup found in Downloads, Desktop or Documents yet." : "Looking…" }));
  out.push(h("div", { class: "actions" },
    h("label", { class: "btn" }, "Choose a file…",
      h("input", { type: "file", accept: ".crypt14,.crypt15,.db", onchange: (e) => upload(e.target.files[0]) })),
    h("button", { class: "btn link", onclick: () => { local.files = null; render(); }, text: "Look again" })));
  if (local.uploading) out.push(busy(`Copying ${local.uploading}…`));

  out.push(h("h2", { text: "4. Enter the key" }));
  const key = h("input", { type: local.show ? "text" : "password", class: "key", id: "android-key", autocomplete: "off",
    spellcheck: "false", placeholder: "64 characters, spaces are fine", value: local.key || "",
    oninput: (e) => { local.key = e.target.value; } });
  out.push(h("div", { class: "field" },
    h("label", { for: "android-key", text: "64-digit key" }),
    h("div", { class: "input-row" }, key,
      h("button", { class: "btn", type: "button", onclick: () => { local.show = !local.show; render(); }, text: local.show ? "Hide" : "Show" })),
    h("div", { class: "hint", text: "Used once to decrypt, then forgotten. Not needed if you picked an already decrypted msgstore.db." })));

  if (local.error) out.push(notice("error", local.error));
  if (local.running) out.push(busy("Decrypting and checking the backup…"));
  out.push(h("div", { class: "actions" },
    h("button", { class: s.android ? "btn" : "btn primary", disabled: !local.path || local.running, onclick: inspectAndroid,
      text: s.android ? "Check again" : "Decrypt and check" }),
    s.android ? nextButton("android") : null));
  if (s.android) out.push(androidResult(s.android));
  return out;
}

async function loadCandidates() {
  ui.android.looking = true;
  try {
    const { files } = await api("GET", "/api/android/candidates");
    ui.android.files = files;
    if (!ui.android.path && files.length) ui.android.path = files[0].path;
  } catch (e) {
    ui.android.files = [];
    ui.android.error = e.message;
  }
  ui.android.looking = false;
  if (current === "android") render();
}

async function upload(file) {
  if (!file) return;
  const local = ui.android;
  local.uploading = file.name;
  local.error = null;
  render();
  try {
    const saved = await api("POST", "/api/android/upload", file);
    local.files = [{ path: saved.path, name: saved.name, size: saved.size, modified: new Date().toISOString() },
      ...(local.files || [])];
    local.path = saved.path;
  } catch (e) {
    local.error = e.message;
  }
  local.uploading = null;
  render();
}

async function inspectAndroid() {
  const local = ui.android;
  local.running = true;
  local.error = null;
  render();
  try {
    await runJob("/api/android/inspect", { path: local.path, key: local.key || "" });
    local.key = "";
    await refresh();
  } catch (e) {
    local.error = e.message;
  }
  local.running = false;
  render();
}

function androidResult(entry) {
  const r = entry.report;
  const header = r.header || {};
  const modern = r.layout.startsWith("modern");
  return h("div", { class: "card result" },
    h("div", { class: "card-head" }, h("span", { class: "badge good", text: "Checked" }), h("h3", { text: entry.source.split(/[\\/]/).pop() })),
    h("p", { class: "muted small", text: `WhatsApp ${header.app_version || "?"} · database version ${r.user_version} · checked ${when(entry.checked_at)}` }),
    modern ? null : notice("warn", r.layout),
    h("p", {}, "Messages from ", h("b", { text: day(r.first_message) }), " to ", h("b", { text: day(r.last_message) }), "."),
    stats(r.counts),
    Object.keys(r.jid_servers || {}).length ? h("details", {},
      h("summary", { text: "Contact identifiers by type" }),
      table(["Server", "Count"], Object.entries(r.jid_servers).map(([k, n]) => [h("td", { class: "path", text: k }), h("td", { class: "num", text: num(n) })]))) : null,
    h("p", { class: "muted small" }, "Decrypted copy: ", h("code", { text: entry.run })));
}

function viewBackup(role) {
  const s = state();
  const local = ui[role];
  const first = role === "before";
  const out = [
    h("h1", { text: first ? "iPhone backup" : "Second iPhone backup" }),
    h("p", { class: "lead", text: first
      ? "A backup shows how WhatsApp on the iPhone stores its data today. The wizard reads it; it never changes it."
      : "With the second account added, a new backup shows which files the new account created. That's where the Android chats will go." }),
  ];
  if (!first && !s.before) {
    out.push(notice("warn", "Check the first iPhone backup before this one."),
      h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => go("before"), text: "Go to the first backup" })));
    return out;
  }
  const platform = BACKUP_STEPS[overview.platform] ? overview.platform : "other";
  out.push(h("h2", { text: first ? "1. Back up the iPhone" : "1. Back up the iPhone again" }),
    h("ol", { class: "instructions" }, BACKUP_STEPS[platform].map((t) => h("li", { text: t }))));
  if (!first) out.push(h("p", { class: "muted", text: "Use the same passphrase as before. The new backup replaces the old one in the same folder; the wizard kept what it needs from the first." }));

  out.push(h("h2", { text: "2. Choose the backup" }));
  if (!local.list && !local.looking) loadBackups(role);
  const list = local.list || { backups: [] };
  if (list.error) out.push(notice("error", list.error));
  if (local.list && !list.backups.length) {
    out.push(notice("info", "No backups found yet", h("div", { class: "small muted", text: overview.backup_roots.length
      ? `Looked in ${overview.backup_roots.join(", ")}.` : "This system has no standard backup folder: set WHATFERRY_BACKUP_ROOT." })));
  }
  if (!local.folder) {
    const preferred = !first && s.before && list.backups.find((b) => b.folder === s.before.folder);
    const pick = preferred || list.backups[0];
    if (pick) local.folder = pick.folder;
  }
  out.push(h("div", { class: "choices", role: "radiogroup", "aria-label": "Backup" },
    list.backups.map((b) => h("label", { class: "choice" },
      h("input", { type: "radio", name: `backup-${role}`, value: b.folder, checked: local.folder === b.folder,
        onchange: () => { local.folder = b.folder; render(); } }),
      h("span", {},
        h("span", { class: "choice-title", text: b.name || "iPhone" }), " ",
        h("span", { class: b.encrypted ? "badge good" : "badge warn", text: b.encrypted ? "Encrypted" : "Not encrypted" }),
        h("div", { class: "choice-meta", text: `${b.model || "?"} · iOS ${b.ios_version || "?"} · backed up ${when(b.backup_date)}` }),
        h("div", { class: "choice-meta", text: b.folder }))))));
  out.push(h("div", { class: "actions" },
    h("button", { class: "btn link", onclick: () => { local.list = null; render(); }, text: "Look again" })));

  const chosen = list.backups.find((b) => b.folder === local.folder);
  if (chosen && !chosen.encrypted) {
    out.push(notice("warn", "This backup isn't encrypted. It's fine for checking, but the transfer will need an encrypted one: tick “Encrypt local backup” and back up again."));
  }
  if (chosen && chosen.encrypted) {
    out.push(h("div", { class: "field" },
      h("label", { for: `pass-${role}`, text: "Backup passphrase" }),
      h("input", { type: "password", id: `pass-${role}`, autocomplete: "off", value: local.passphrase || "",
        oninput: (e) => { local.passphrase = e.target.value; } }),
      h("div", { class: "hint", text: "The one you chose when you ticked “Encrypt local backup”. Used once, never saved." })));
  }
  if (local.error) out.push(notice("error", local.error));
  if (local.running) {
    out.push(busy(chosen && chosen.encrypted
      ? "Unlocking the backup. This takes a minute or two: the slow part is the encryption doing its job."
      : "Reading the backup…"));
  }
  out.push(h("div", { class: "actions" },
    h("button", { class: s[role] ? "btn" : "btn primary", disabled: !chosen || local.running,
      onclick: () => inspectBackup(role, chosen),
      text: s[role] ? "Check again" : first ? "Check this backup" : "Check and compare" }),
    s[role] ? nextButton(role) : null));
  if (s[role]) out.push(backupResult(s[role], role));
  return out;
}

async function loadBackups(role) {
  ui[role].looking = true;
  try {
    ui[role].list = await api("GET", "/api/ios/backups");
  } catch (e) {
    ui[role].list = { backups: [], error: e.message };
  }
  ui[role].looking = false;
  if (current === role) render();
}

async function inspectBackup(role, chosen) {
  const local = ui[role];
  local.running = true;
  local.error = null;
  render();
  try {
    await runJob("/api/ios/inspect", { folder: chosen.folder, passphrase: chosen.encrypted ? (local.passphrase || "") : null, role });
    local.passphrase = "";
    await refresh();
  } catch (e) {
    local.error = e.message;
  }
  local.running = false;
  render();
}

function backupResult(entry, role) {
  const r = entry.report;
  const d = r.device;
  const stores = r.databases.filter((db) => db.path.split("/").pop() === "ChatStorage.sqlite");
  const parts = [
    h("div", { class: "card-head" }, h("span", { class: "badge good", text: "Checked" }), h("h3", { text: d.name || "iPhone" })),
    h("p", { class: "muted small", text: `${d.model || "?"} · iOS ${d.ios_version || "?"} · backed up ${when(d.backup_date)} · checked ${when(entry.checked_at)}` }),
  ];
  if (!Object.keys(r.domains).length) parts.push(notice("warn", "This backup has no WhatsApp data. Is WhatsApp installed on this iPhone?"));
  // After adding the account, what changed is the answer; the stores come second.
  if (entry.diff) parts.push(diffResult(entry.diff));
  for (const store of stores) {
    parts.push(h("h3", {}, "Chats in ", h("code", { text: store.path })),
      h("p", { class: "muted small", text: store.first_message
        ? `Messages from ${day(store.first_message)} to ${day(store.last_message)}` : "No messages yet." }),
      stats(store.counts));
  }
  if (stores.length > 1) parts.push(notice("info", `${stores.length} chat databases: probably one per account.`));
  parts.push(h("details", {},
    h("summary", { text: "WhatsApp's storage areas" }),
    table(["Area", "Files", "Size"], Object.entries(r.domains).map(([domain, n]) => [
      h("td", { class: "path", text: domain }), h("td", { class: "num", text: num(n.files) }), h("td", { class: "num", text: size(n.bytes) })]))));
  if (role === "before") parts.push(h("p", { class: "muted small", text: "Saved this backup's file list, to compare with the next backup." }));
  return h("div", { class: "card result" }, parts);
}

function diffResult(diff) {
  const found = diff.new_chat_storages.length;
  return h("div", {},
    h("h3", { text: "What adding the account changed" }),
    stats({ "files added": diff.added, "files changed": diff.changed, "files removed": diff.removed }),
    found
      ? notice("info", h("b", { text: found === 1 ? "Found the new account's chat database:" : `Found ${found} new chat databases:` }),
        h("div", { class: "path-list", text: diff.new_chat_storages.join("\n") }),
        "That's where the Android chats will go.")
      : notice("warn", "No new chat database appeared. The second account may share the existing one, or WhatsApp hadn't finished setting it up before the backup. The full list of changes is below."),
    table(["Where", "Added", "Changed", "Removed"], Object.entries(diff.by_folder).map(([folder, c]) => [
      h("td", { class: "path", text: folder }), h("td", { class: "num", text: num(c.added || 0) }),
      h("td", { class: "num", text: num(c.changed || 0) }), h("td", { class: "num", text: num(c.removed || 0) })])),
    diff.added_paths.length ? h("details", {}, h("summary", { text: "Files added" }),
      h("div", { class: "path-list", text: diff.added_paths.join("\n") })) : null,
    diff.changed_paths.length ? h("details", {}, h("summary", { text: "Files changed" }),
      h("div", { class: "path-list", text: diff.changed_paths.join("\n") })) : null);
}

function viewAccount() {
  const list = state().checklist || {};
  const allDone = CHECKLIST.every(([key]) => list[key]);
  return [
    h("h1", { text: "Add the Android number on the iPhone" }),
    h("p", { class: "lead", text: "WhatsApp sets up the second account itself: its own empty database, folders and keys. Later, only that new account is filled with the Android chats; your current account isn't touched." }),
    h("div", { class: "card" }, CHECKLIST.map(([key, text]) => h("label", { class: "check" },
      h("input", { type: "checkbox", checked: Boolean(list[key]), onchange: (e) => tick(key, e.target.checked) }),
      h("span", { text })))),
    notice("warn", "Keep WhatsApp installed on the Android phone until the transfer is finished. If anything goes wrong you can sign back in there and your chats are still on it."),
    h("div", { class: "actions" }, h("button", { class: allDone ? "btn primary" : "btn", onclick: () => go("after"),
      text: allDone ? "Continue" : "Continue anyway" })),
  ];
}

async function tick(item, done) {
  try {
    const { checklist } = await api("POST", "/api/checklist", { item, done });
    overview.state.checklist = checklist;
  } catch { /* the checkbox still shows what was clicked */ }
  render();
}

function viewDone() {
  const out = [
    h("h1", { text: "Results" }),
    h("p", { class: "lead", text: "This summary holds counts, versions and file locations: no messages, names or phone numbers. Send it on so the transfer can be built for this exact setup." }),
  ];
  const area = h("textarea", { readonly: true, "aria-label": "Summary", text: "Loading…" });
  api("GET", "/api/summary").then(({ text }) => { area.value = text; }).catch((e) => { area.value = e.message; });
  const copied = h("span", { class: "muted small", role: "status" });
  out.push(area, h("div", { class: "actions" },
    h("button", { class: "btn primary", text: "Copy summary", onclick: async () => {
      try { await navigator.clipboard.writeText(area.value); } catch { area.select(); document.execCommand("copy"); }
      copied.textContent = "Copied.";
    } }), copied));
  out.push(h("h2", { text: "What happens next" }),
    h("p", { text: "The step that writes the Android chats into the new account isn't built yet. These results are what it will be built from." }),
    h("h2", { text: "Cleaning up" }),
    h("p", {}, "Decrypted copies are in ", h("code", { text: overview.home }), ". Delete that folder whenever you like; the summary above doesn't need it."),
    h("div", { class: "actions" }, h("button", { class: "btn", text: "Start over", onclick: startOver })));
  return out;
}

async function startOver() {
  if (!confirm("Forget all progress? Decrypted copies stay on disk until you delete them.")) return;
  await api("POST", "/api/reset", {});
  Object.assign(ui, { android: {}, before: {}, after: {} });
  await refresh();
  go("start");
}

// ---- Start ----

async function start() {
  const main = document.getElementById("main");
  if (!TOKEN) {
    main.replaceChildren(h("p", { class: "loading", text: "Open the wizard with the link `whatferry ui` printed." }));
    return;
  }
  try {
    await refresh();
  } catch (e) {
    main.replaceChildren(notice("error", `Can't reach whatferry: ${e.message}. Is \`whatferry ui\` still running?`));
    return;
  }
  const saved = state().step;
  current = STEPS.some((s) => s.id === saved) ? saved : "start";
  render();
}

start();
