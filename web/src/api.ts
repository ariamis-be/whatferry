// Talks only to the local whatferry server that served this page, with the
// token from the link `whatferry ui` opened.

export const TOKEN = new URLSearchParams(location.search).get("t") ?? ""

export type Counts = Record<string, number | null>

export interface AndroidReport {
  source: string
  header: { app_version: string | null; number_ends_with: string | null } | null
  user_version: number
  layout: string
  counts: Counts
  jid_servers: Record<string, number>
  message_types: Record<string, number>
  first_message: string | null
  last_message: string | null
  tables: number
}

export interface AndroidEntry {
  source: string
  run: string
  checked_at: string
  report: AndroidReport
}

export interface Device {
  name: string | null
  model: string | null
  ios_version: string | null
  backup_date: string | null
  encrypted: boolean
}

export interface Database {
  domain: string
  path: string
  size: number
  user_version: number
  tables: number
  counts: Counts
  first_message: string | null
  last_message: string | null
}

export interface IphoneAccount {
  id_ends: string | null
  number_ends: string | null
  country: string | null
  main: boolean
  folder?: string | null
  has_chats?: boolean
}

export interface IosReport {
  device: Device
  domains: Record<string, { files: number; bytes: number }>
  databases: Database[]
  accounts?: IphoneAccount[]
  account_folders?: { folder: string; has_chat_database: boolean }[]
}

export type Destination = "setup" | "second" | "existing"

export interface DestinationHint {
  suggested: Destination
  reason: "no-whatsapp" | "number-matches" | "different-number" | "unknown-number" | "stale-check" | "iphone-numbers-unknown" | "second-started"
  stale?: boolean
  android_ends: string | null
  accounts: IphoneAccount[]
  full: boolean
  match?: IphoneAccount
  messages?: number | null
  main_messages?: number | null
  has_whatsapp?: boolean
}

export interface Diff {
  added: number
  removed: number
  changed: number
  by_folder: Record<string, { added?: number; changed?: number; removed?: number }>
  added_paths: string[]
  changed_paths: string[]
  new_chat_storages: string[]
}

export interface IosEntry {
  folder: string
  run: string
  checked_at: string
  report: IosReport
  snapshot?: string
  diff?: Diff
}

export interface State {
  step?: string
  android?: AndroidEntry
  before?: IosEntry
  after?: IosEntry
  destination?: Destination
  direction?: Direction
  converted?: ConvertedEntry
  written?: WrittenEntry
  restored?: RestoredEntry
}

export type Direction = "to-iphone" | "to-android"

export interface Compatibility {
  kind: string
  ok: boolean
  tested: boolean
  version: string | null
  note: string | null
}

/** Either direction's report: Android -> iPhone counts android_messages, iPhone -> Android iphone_messages. */
export interface ConvertReport {
  direction?: "iphone-to-android"
  android_messages?: number
  iphone_messages?: number
  checks_before?: Record<string, unknown>
  compatibility?: Compatibility[]
  converted: Record<string, number>
  skipped: Record<string, number>
  already_there: number
  chats_matched: number
  chats_created: number
  groups_created: number
  members_created: number
  media_rows: number
  media_files_copied: number
  media_files_missing: number
  not_converted_yet?: Record<string, number>
  checks: Record<string, unknown>
}

export interface ConvertedEntry {
  run: string
  backup: string
  account_folder: string | null
  media: string | null
  made_at: string
  report: ConvertReport
  direction?: Direction
  // iPhone -> Android: the msgstore.db.crypt15 the conversion is written back like.
  android_source?: string
}

export interface WrittenEntry {
  folder: string
  from: string
  made_at: string
  direction?: Direction
  report: {
    source_checked: boolean
    // Android -> iPhone
    encrypted?: boolean
    added_files?: number
    added_bytes?: number
    verified_files?: number
    // iPhone -> Android
    backup_bytes?: number
    media_files?: number
    verified?: boolean
  }
}

export interface RestoredEntry {
  folder: string
  phone: string | null
  restored_at: string
  // iPhone -> Android: where on the phone it went, and the phone's own backup kept.
  root?: string
  kept?: string | null
  media_files?: number
}

export interface AndroidPhone {
  serial: string
  model: string | null
  ready: boolean
  advice: string | null
  folders?: string[]
  error?: string
}

export interface AndroidPhones {
  direction: "to-android"
  adb: string | null
  devices: AndroidPhone[]
  error?: string | null
  suggested_folder: string
}

export interface ConvertTarget {
  folder: string | null
  main: boolean
  number_ends: string | null
  country: string | null
  messages: number | null
  suggested: boolean
}

export interface MediaFolder {
  path: string
  name: string
  found: number
  sampled: number
  suggested: boolean
}

export interface ConvertOptions {
  direction: Direction
  backup: string
  backup_checked_at: string
  targets: ConvertTarget[]
  // Android -> iPhone
  second_backup?: boolean
  media?: MediaFolder[]
  // iPhone -> Android: media come out of the iPhone backup, which may need its passphrase.
  encrypted?: boolean
  android_ready?: boolean
}

export interface ConnectedIphone {
  udid: string
  name: string | null
  ios_version: string | null
  paired: boolean
  find_my: boolean | null
}

export interface RestoreStatus {
  phones: ConnectedIphone[]
  error: string | null
  udid: string | null
}

export interface Overview {
  platform: string
  how_to_back_up: string
  backup_roots: string[]
  home: string
  candidate_folders: string[]
  phone_folder: string
  state: State
  destination_hint: DestinationHint | null
  android_accounts: AndroidAccount[]
}

export interface AndroidAccount {
  key: string
  name: string
  number_ends: string | null
  messages: number | null
  destination: Destination | null
  second_backup_checked: boolean
  current: boolean
}

export interface PhoneBackup {
  path: string
  name: string
  size: number
  modified: string
  app: string
  account: string | null
  kind: string
  usable: boolean
  note: string | null
  local_name: string
}

export interface Phone {
  serial: string
  state: string
  model: string | null
  ready: boolean
  advice: string | null
  backups?: PhoneBackup[]
  error?: string
}

export interface PhoneStatus {
  adb: string | null
  devices: Phone[]
  error?: string
}

export interface Candidate {
  path: string
  name: string
  size: number
  modified: string
}

export interface BackupListing extends Device {
  folder: string
  id: string
}

export async function api<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-Whatferry-Token": TOKEN }
  let payload: BodyInit | undefined
  if (body instanceof File) {
    payload = body
    headers["Content-Type"] = "application/octet-stream"
    headers["X-Filename"] = encodeURIComponent(body.name)
  } else if (body !== undefined) {
    payload = JSON.stringify(body)
    headers["Content-Type"] = "application/json"
  }
  const res = await fetch(path, { method, headers, body: payload })
  let data: { error?: string } = {}
  try {
    data = await res.json()
  } catch {
    // not JSON
  }
  if (!res.ok) throw new Error(data.error ?? `request failed (${res.status})`)
  return data as T
}

/** Start a background job and wait for it, polling. */
export async function runJob<T>(path: string, body: unknown, onProgress?: (percent: number) => void): Promise<T> {
  const { job } = await api<{ job: string }>("POST", path, body)
  for (;;) {
    await new Promise((r) => setTimeout(r, 600))
    const status = await api<{ status: string; result?: T; error?: string; progress?: number }>("GET", `/api/jobs/${job}`)
    if (status.progress !== undefined) onProgress?.(status.progress)
    if (status.status === "done") return status.result as T
    if (status.status === "error") throw new Error(status.error)
  }
}

// Dates and numbers follow the page's language, set by the language picker.
let currentLocale: string | undefined
export function setLocale(locale: string) {
  currentLocale = locale
}

export const num = (n: number | null | undefined) => (typeof n === "number" ? n.toLocaleString(currentLocale) : "?")

export function size(bytes: number | null | undefined) {
  if (typeof bytes !== "number") return "?"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${i ? bytes.toFixed(1) : bytes} ${units[i]}`
}

export function when(iso: string | null | undefined) {
  if (!iso) return "?"
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString(currentLocale, { dateStyle: "medium", timeStyle: "short" })
}

export function day(iso: string | null | undefined) {
  if (!iso) return "?"
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString(currentLocale, { dateStyle: "medium" })
}

export type ChatChange = "new" | "joined" | "unchanged"

export interface PreviewChat {
  id: number
  name: string
  jid: string
  group: boolean
  change: ChatChange
  messages: number
  moved: number
  first: string | null
  last: string | null
}

export interface PreviewChats {
  chats: PreviewChat[]
  totals: Record<ChatChange | "moved", number>
}

export interface PreviewMessage {
  id: number
  at: string | null
  from_me: boolean
  sender: string | null
  kind: string
  text: string | null
  moved: boolean
  picture: boolean
}

/** The page's language and theme, kept by the server across restarts. */
export interface Settings {
  lang?: string
  theme?: string
}

export function saveSettings(settings: Settings) {
  // Not saved (server gone): the choice still applies for this visit.
  api("POST", "/api/settings", settings).catch(() => {})
}
