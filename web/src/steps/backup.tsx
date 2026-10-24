import { useCallback, useEffect, useState } from "react"
import { ArrowRight, CircleCheck, FolderSearch, Info, Lock, RefreshCw, TriangleAlert } from "lucide-react"

import { api, day, num, runJob, size, when, type BackupListing, type Diff, type IosEntry } from "@/api"
import { Busy, Disclosure, ErrorNotice, Instructions, PageHeader, Path, Section, StatGrid } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { nextStep, type StepProps } from "@/wizard"

const BACKUP_STEPS: Record<string, string[]> = {
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
}

interface Listing {
  backups: BackupListing[]
  error: string | null
}

function findBackups(): Promise<Listing> {
  return api<Listing>("GET", "/api/ios/backups").catch((e: Error) => ({ backups: [], error: e.message }))
}

export function BackupStep({ overview, refresh, go, role }: StepProps & { role: "before" | "after" }) {
  const first = role === "before"
  const state = overview.state
  const checked = state[role]
  const [listing, setListing] = useState<Listing | null>(null)
  const [folder, setFolder] = useState("")
  const [passphrase, setPassphrase] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const beforeFolder = state.before?.folder
  const show = useCallback(
    (found: Listing) => {
      setListing(found)
      setFolder((current) => {
        if (current && found.backups.some((b) => b.folder === current)) return current
        const same = !first && found.backups.find((b) => b.folder === beforeFolder)
        return (same || found.backups[0])?.folder ?? ""
      })
    },
    [first, beforeFolder],
  )

  useEffect(() => {
    let live = true
    findBackups().then((found) => live && show(found))
    return () => {
      live = false
    }
  }, [show])

  function look() {
    setListing(null)
    findBackups().then(show)
  }

  if (!first && !state.before) {
    return (
      <>
        <PageHeader title="Second iPhone backup" lead="Check the first iPhone backup before this one." />
        <Button variant="outline" onClick={() => go("before")}>
          Go to the first backup
        </Button>
      </>
    )
  }

  const chosen = listing?.backups.find((b) => b.folder === folder)
  const steps = BACKUP_STEPS[overview.platform] ?? BACKUP_STEPS.other

  async function inspect() {
    if (!chosen) return
    setBusy(
      chosen.encrypted
        ? "Unlocking the backup. This takes a minute or two: the slow part is the encryption doing its job."
        : "Reading the backup…",
    )
    setError(null)
    try {
      await runJob("/api/ios/inspect", { folder: chosen.folder, passphrase: chosen.encrypted ? passphrase : null, role })
      setPassphrase("")
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(null)
  }

  return (
    <>
      <PageHeader
        title={first ? "iPhone backup" : "Second iPhone backup"}
        lead={
          first
            ? "A backup shows how WhatsApp on the iPhone stores its data today. The wizard reads it; it never changes it."
            : "With the second account added, a new backup shows which files the new account created. That's where the Android chats will go."
        }
      />

      <Section n={1} title={first ? "Back up the iPhone" : "Back up the iPhone again"}>
        <Instructions items={steps} />
        {!first && (
          <p className="text-sm text-muted-foreground">
            Use the same passphrase as before. The new backup replaces the old one in the same folder; the wizard kept
            what it needs from the first.
          </p>
        )}
      </Section>

      <Section n={2} title="Choose the backup">
        <ErrorNotice message={listing?.error} />
        {listing === null ? (
          <Busy>Looking for backups…</Busy>
        ) : listing.backups.length === 0 ? (
          <Alert>
            <FolderSearch />
            <AlertTitle>No backups found yet</AlertTitle>
            <AlertDescription>
              {overview.backup_roots.length
                ? `Looked in ${overview.backup_roots.join(", ")}.`
                : "This system has no standard backup folder: set WHATFERRY_BACKUP_ROOT."}
            </AlertDescription>
          </Alert>
        ) : (
          <RadioGroup value={folder} onValueChange={setFolder} aria-label="Backup">
            {listing.backups.map((b) => (
              <Label
                key={b.folder}
                htmlFor={`${role}-${b.folder}`}
                className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-muted/50"
              >
                <RadioGroupItem value={b.folder} id={`${role}-${b.folder}`} className="mt-0.5" />
                <span className="grid min-w-0 gap-1">
                  <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {b.name ?? "iPhone"}
                    {b.encrypted ? (
                      <Badge variant="secondary">
                        <Lock data-icon="inline-start" /> Encrypted
                      </Badge>
                    ) : (
                      <Badge variant="outline">Not encrypted</Badge>
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {b.model ?? "?"} · iOS {b.ios_version ?? "?"} · backed up {when(b.backup_date)}
                  </span>
                  <Path>{b.folder}</Path>
                </span>
              </Label>
            ))}
          </RadioGroup>
        )}
        <Button variant="ghost" onClick={look}>
          <RefreshCw data-icon="inline-start" /> Look again
        </Button>

        {chosen && !chosen.encrypted && (
          <Alert>
            <TriangleAlert />
            <AlertTitle>This backup isn't encrypted</AlertTitle>
            <AlertDescription>
              It's fine for checking, but the transfer will need an encrypted one: tick “Encrypt local backup” and back
              up again.
            </AlertDescription>
          </Alert>
        )}
        {chosen?.encrypted && (
          <div className="grid gap-2">
            <Label htmlFor={`pass-${role}`}>Backup passphrase</Label>
            <Input
              id={`pass-${role}`}
              type="password"
              autoComplete="off"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              The one you chose when you ticked “Encrypt local backup”. Used once, never saved.
            </p>
          </div>
        )}
      </Section>

      <ErrorNotice message={error} />
      {busy && <Busy>{busy}</Busy>}

      <div className="flex flex-wrap gap-2">
        <Button size="lg" variant={checked ? "outline" : "default"} disabled={!chosen || busy !== null} onClick={inspect}>
          {checked ? "Check again" : first ? "Check this backup" : "Check and compare"}
        </Button>
        {checked && (
          <Button size="lg" onClick={() => go(nextStep(role))}>
            Continue <ArrowRight data-icon="inline-end" />
          </Button>
        )}
      </div>

      {checked && <BackupResult entry={checked} first={first} />}
    </>
  )
}

function BackupResult({ entry, first }: { entry: IosEntry; first: boolean }) {
  const r = entry.report
  const d = r.device
  const stores = r.databases.filter((db) => db.path.split("/").pop() === "ChatStorage.sqlite")
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CircleCheck className="size-4 text-primary" />
          {d.name ?? "iPhone"}
          <Badge variant="secondary">Checked</Badge>
        </CardTitle>
        <CardDescription>
          {d.model ?? "?"} · iOS {d.ios_version ?? "?"} · backed up {when(d.backup_date)} · checked {when(entry.checked_at)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {Object.keys(r.domains).length === 0 && (
          <Alert>
            <TriangleAlert />
            <AlertDescription>This backup has no WhatsApp data. Is WhatsApp installed on this iPhone?</AlertDescription>
          </Alert>
        )}
        {entry.diff && <DiffView diff={entry.diff} />}
        {stores.map((store) => (
          <div key={store.path} className="space-y-3">
            <div>
              <h3 className="text-sm font-medium">
                Chats in <code className="font-mono text-xs">{store.path}</code>
              </h3>
              <p className="text-xs text-muted-foreground">
                {store.first_message
                  ? `Messages from ${day(store.first_message)} to ${day(store.last_message)}`
                  : "No messages yet."}
              </p>
            </div>
            <StatGrid counts={store.counts} />
          </div>
        ))}
        {stores.length > 1 && (
          <Alert>
            <Info />
            <AlertDescription>{stores.length} chat databases: probably one per account.</AlertDescription>
          </Alert>
        )}
        <Disclosure title="WhatsApp's storage areas">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Area</TableHead>
                  <TableHead className="text-right">Files</TableHead>
                  <TableHead className="text-right">Size</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(r.domains).map(([domain, n]) => (
                  <TableRow key={domain}>
                    <TableCell className="font-mono text-xs whitespace-normal break-all">{domain}</TableCell>
                    <TableCell className="text-right tabular-nums">{num(n.files)}</TableCell>
                    <TableCell className="text-right tabular-nums">{size(n.bytes)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
        </Disclosure>
        {first && (
          <p className="text-xs text-muted-foreground">Saved this backup's file list, to compare with the next backup.</p>
        )}
      </CardContent>
    </Card>
  )
}

function DiffView({ diff }: { diff: Diff }) {
  const found = diff.new_chat_storages.length
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium">What adding the account changed</h3>
      <StatGrid
        className="sm:grid-cols-3"
        counts={{ "files added": diff.added, "files changed": diff.changed, "files removed": diff.removed }}
      />
      {found ? (
        <Alert>
          <CircleCheck />
          <AlertTitle>
            {found === 1 ? "Found the new account's chat database" : `Found ${found} new chat databases`}
          </AlertTitle>
          <AlertDescription className="space-y-2">
            {diff.new_chat_storages.map((p) => (
              <Path key={p} className="block text-foreground">
                {p}
              </Path>
            ))}
            <span className="block">That's where the Android chats will go.</span>
          </AlertDescription>
        </Alert>
      ) : (
        <Alert>
          <TriangleAlert />
          <AlertTitle>No new chat database appeared</AlertTitle>
          <AlertDescription>
            The second account may share the existing one, or WhatsApp hadn't finished setting it up before the backup.
            The full list of changes is below.
          </AlertDescription>
        </Alert>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Where</TableHead>
            <TableHead className="text-right">Added</TableHead>
            <TableHead className="text-right">Changed</TableHead>
            <TableHead className="text-right">Removed</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(diff.by_folder).map(([where, c]) => (
            <TableRow key={where}>
              <TableCell className="font-mono text-xs whitespace-normal break-all">{where}</TableCell>
              <TableCell className="text-right tabular-nums">{c.added ?? 0}</TableCell>
              <TableCell className="text-right tabular-nums">{c.changed ?? 0}</TableCell>
              <TableCell className="text-right tabular-nums">{c.removed ?? 0}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {[
        ["Files added", diff.added_paths],
        ["Files changed", diff.changed_paths],
      ].map(([title, paths]) =>
        (paths as string[]).length ? (
          <Disclosure key={title as string} title={title as string}>
            <pre className="max-h-72 overflow-auto rounded-lg bg-muted p-3 font-mono text-xs wrap-anywhere whitespace-pre-wrap">
              {(paths as string[]).join("\n")}
            </pre>
          </Disclosure>
        ) : null,
      )}
      <Separator />
    </div>
  )
}
