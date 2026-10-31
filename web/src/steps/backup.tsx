import { useCallback, useEffect, useState } from "react"
import { CircleCheck, FolderSearch, Info, Lock, RefreshCw, TriangleAlert } from "lucide-react"

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
import { useI18n } from "@/i18n"
import { DestinationChoice } from "@/steps/destination"
import { platformOf, type StepProps } from "@/wizard"

interface Listing {
  backups: BackupListing[]
  error: string | null
}

function findBackups(): Promise<Listing> {
  return api<Listing>("GET", "/api/ios/backups").catch((e: Error) => ({ backups: [], error: e.message }))
}

export function BackupStep({ overview, refresh, go, role }: StepProps & { role: "before" | "after" }) {
  const { t } = useI18n()
  const first = role === "before"
  const state = overview.state
  const toAndroid = state.direction === "to-android"
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

  if (!first && state.destination === "existing") {
    return (
      <>
        <PageHeader title={t.backup.title.after} lead={t.account.notNeeded} />
        <p className="text-sm">{t.account.skipNote}</p>
      </>
    )
  }

  if (!first && !state.before) {
    return (
      <>
        <PageHeader title={t.backup.title.after} lead={t.backup.needFirst} />
        <Button variant="outline" onClick={() => go("before")}>
          {t.backup.goFirst}
        </Button>
      </>
    )
  }

  const chosen = listing?.backups.find((b) => b.folder === folder)

  async function inspect() {
    if (!chosen) return
    setBusy(chosen.encrypted ? t.backup.unlocking : t.backup.reading)
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
      <PageHeader title={t.backup.title[role]} lead={t.backup.lead[role]} />

      <Section n={1} title={t.backup.makeTitle[role]}>
        <Instructions items={t.backup.make[platformOf(overview)]} />
        {!first && <p className="text-sm text-muted-foreground">{t.backup.samePassphrase}</p>}
      </Section>

      <Section n={2} title={t.backup.chooseTitle}>
        <ErrorNotice message={listing?.error} />
        {listing === null ? (
          <Busy>{t.backup.looking}</Busy>
        ) : listing.backups.length === 0 ? (
          <Alert>
            <FolderSearch />
            <AlertTitle>{t.backup.noneTitle}</AlertTitle>
            <AlertDescription>
              {overview.backup_roots.length ? t.backup.lookedIn(overview.backup_roots.join(", ")) : t.backup.noRoot}
            </AlertDescription>
          </Alert>
        ) : (
          <RadioGroup value={folder} onValueChange={setFolder} aria-label={t.backup.chooseTitle}>
            {listing.backups.map((b) => (
              <Label
                key={b.folder}
                htmlFor={`${role}-${b.folder}`}
                className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-muted/50"
              >
                <RadioGroupItem value={b.folder} id={`${role}-${b.folder}`} className="mt-0.5" />
                <span className="grid min-w-0 gap-1">
                  <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {b.name ?? t.backup.iphone}
                    {b.encrypted ? (
                      <Badge variant="secondary">
                        <Lock data-icon="inline-start" /> {t.backup.encrypted}
                      </Badge>
                    ) : (
                      <Badge variant="outline">{t.backup.notEncrypted}</Badge>
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {t.backup.deviceLine(b.model ?? "?", b.ios_version ?? "?", when(b.backup_date))}
                  </span>
                  <Path>{b.folder}</Path>
                </span>
              </Label>
            ))}
          </RadioGroup>
        )}
        <Button variant="ghost" onClick={look}>
          <RefreshCw data-icon="inline-start" /> {t.common.searchAgain}
        </Button>

        {chosen && !chosen.encrypted && (
          <Alert>
            <TriangleAlert />
            <AlertTitle>{t.backup.notEncryptedTitle}</AlertTitle>
            <AlertDescription>{t.backup.notEncryptedBody}</AlertDescription>
          </Alert>
        )}
        {chosen?.encrypted && (
          <div className="grid gap-2">
            <Label htmlFor={`pass-${role}`}>{t.backup.passLabel}</Label>
            <Input
              id={`pass-${role}`}
              type="password"
              autoComplete="off"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t.backup.passHint}</p>
          </div>
        )}
      </Section>

      <div className="space-y-4">
        <ErrorNotice message={error} />
        {busy && <Busy>{busy}</Busy>}
        <Button variant={checked ? "outline" : "default"} disabled={!chosen || busy !== null} onClick={inspect}>
          {checked ? t.backup.checkAgain : t.backup.check[role]}
        </Button>
        {/* iPhone -> Android has no second backup to compare with, and no question of where chats go. */}
        {checked && <BackupResult entry={checked} first={first && !toAndroid} />}
        {first && checked && !toAndroid && <DestinationChoice overview={overview} refresh={refresh} />}
      </div>
    </>
  )
}

function BackupResult({ entry, first }: { entry: IosEntry; first: boolean }) {
  const { t } = useI18n()
  const r = entry.report
  const d = r.device
  const stores = r.databases.filter((db) => db.path.split("/").pop() === "ChatStorage.sqlite")
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CircleCheck className="size-4 text-primary" />
          {d.name ?? t.backup.iphone}
          <Badge variant="secondary">{t.common.checked}</Badge>
        </CardTitle>
        <CardDescription>
          {t.backup.resultLine(d.model ?? "?", d.ios_version ?? "?", when(d.backup_date), when(entry.checked_at))}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {Object.keys(r.domains).length === 0 && (
          <Alert>
            <TriangleAlert />
            <AlertDescription>{t.backup.noWhatsapp}</AlertDescription>
          </Alert>
        )}
        {entry.diff && <DiffView diff={entry.diff} />}
        {stores.map((store) => (
          <div key={store.path} className="space-y-3">
            <div>
              <h3 className="text-sm font-medium">{t.backup.chatsIn(store.path)}</h3>
              <p className="text-xs text-muted-foreground">
                {store.first_message
                  ? t.backup.messagesRange(day(store.first_message), day(store.last_message))
                  : t.common.noMessages}
              </p>
            </div>
            <StatGrid counts={store.counts} />
          </div>
        ))}
        {stores.length > 1 && (
          <Alert>
            <Info />
            <AlertDescription>{t.backup.manyStores(stores.length)}</AlertDescription>
          </Alert>
        )}
        <Disclosure title={t.backup.areasTitle}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t.backup.areasHead[0]}</TableHead>
                <TableHead className="text-right">{t.backup.areasHead[1]}</TableHead>
                <TableHead className="text-right">{t.backup.areasHead[2]}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(r.domains).map(([domain, n]) => (
                <TableRow key={domain}>
                  <TableCell className="font-mono text-xs whitespace-nowrap">{domain}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(n.files)}</TableCell>
                  <TableCell className="text-right tabular-nums">{size(n.bytes)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Disclosure>
        {first && <p className="text-xs text-muted-foreground">{t.backup.savedList}</p>}
      </CardContent>
    </Card>
  )
}

function DiffView({ diff }: { diff: Diff }) {
  const { t } = useI18n()
  const found = diff.new_chat_storages.length
  const lists: [string, string[]][] = [
    [t.backup.filesAdded, diff.added_paths],
    [t.backup.filesChanged, diff.changed_paths],
  ]
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium">{t.backup.diffTitle}</h3>
      <StatGrid
        className="sm:grid-cols-3"
        counts={{ "files added": diff.added, "files changed": diff.changed, "files removed": diff.removed }}
      />
      {found ? (
        <Alert>
          <CircleCheck />
          <AlertTitle>{found === 1 ? t.backup.foundOne : t.backup.foundMany(found)}</AlertTitle>
          <AlertDescription className="space-y-2">
            {diff.new_chat_storages.map((p) => (
              <Path key={p} className="block overflow-x-auto whitespace-nowrap text-foreground">
                {p}
              </Path>
            ))}
            <span className="block">{t.backup.whereGo}</span>
          </AlertDescription>
        </Alert>
      ) : (
        <Alert>
          <TriangleAlert />
          <AlertTitle>{t.backup.noneNewTitle}</AlertTitle>
          <AlertDescription>{t.backup.noneNewBody}</AlertDescription>
        </Alert>
      )}
      {/* Counts first: the folder names run long and scroll, the numbers stay in view. */}
      <Table>
        <TableHeader>
          <TableRow>
            {t.backup.diffHead.slice(1).map((head) => (
              <TableHead key={head} className="w-0 text-right">
                {head}
              </TableHead>
            ))}
            <TableHead>{t.backup.diffHead[0]}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(diff.by_folder).map(([where, c]) => (
            <TableRow key={where}>
              <TableCell className="text-right tabular-nums">{c.added ?? 0}</TableCell>
              <TableCell className="text-right tabular-nums">{c.changed ?? 0}</TableCell>
              <TableCell className="text-right tabular-nums">{c.removed ?? 0}</TableCell>
              <TableCell className="font-mono text-xs whitespace-nowrap">{where}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {lists.map(([title, paths]) =>
        paths.length ? (
          <Disclosure key={title} title={title}>
            <pre className="max-h-72 overflow-auto rounded-lg bg-muted p-3 font-mono text-xs whitespace-pre">
              {paths.join("\n")}
            </pre>
          </Disclosure>
        ) : null,
      )}
      <Separator />
    </div>
  )
}
