import { useEffect, useState } from "react"
import { CircleCheck, Info, TriangleAlert } from "lucide-react"

import { api, num, runJob, when, type ConvertOptions, type ConvertTarget, type ConvertedEntry } from "@/api"
import { Busy, ErrorNotice, PageHeader, Path, Section, StatGrid } from "@/components/bits"
import { ConversionPreview } from "@/components/preview"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { useI18n } from "@/i18n"
import type { StepProps } from "@/wizard"

// Radio values: an account's folder, or MAIN for the main account; a media
// folder's path, or one of the choices that aren't a listed folder.
const MAIN = "main"
const OTHER = "other"
const NONE = "none"
const BACKUP = "backup"

// Counts in the checks that are problems when they grow.
const SUMMARY_CHECKS = new Set(["integrity", "messages", "chats", "first message", "last message"])

const OPTION =
  "flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-muted/50"

// The count labels are lower case for the stat tiles; a list line starts with a capital.
function capitalized(label: string) {
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function ConvertStep({ overview, refresh, go }: StepProps) {
  const { t } = useI18n()
  const state = overview.state
  const toAndroid = state.direction === "to-android"
  const ready = Boolean(state.android && (toAndroid ? state.before : state.after || state.before))
  const [options, setOptions] = useState<ConvertOptions | null>(null)
  const [target, setTarget] = useState("")
  const [media, setMedia] = useState("")
  const [otherMedia, setOtherMedia] = useState("")
  const [passphrase, setPassphrase] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!ready) return
    let live = true
    api<ConvertOptions>("GET", "/api/convert/options")
      .then((o) => {
        if (!live) return
        setOptions(o)
        const done = state.converted
        const suggested = o.targets.find((x) => x.suggested)
        setTarget(done ? (done.account_folder ?? MAIN) : suggested ? (suggested.folder ?? MAIN) : "")
        if (o.direction === "to-android") {
          setMedia(done && !done.media ? NONE : BACKUP)
          return
        }
        const folders = o.media ?? []
        const listed = folders.find((m) => (done ? m.path === done.media : m.suggested))
        if (listed) setMedia(listed.path)
        else if (done?.media) {
          setMedia(OTHER)
          setOtherMedia(done.media)
        } else setMedia(folders.length ? "" : NONE)
      })
      .catch((e: Error) => live && setError(e.message))
    return () => {
      live = false
    }
    // Options load once per visit; a conversion refreshes the state, not them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready])

  if (!ready) {
    const missing = toAndroid ? (state.before ? "android" : "before") : state.android ? "before" : "android"
    return (
      <>
        <PageHeader title={t.convert.title} lead={t.convert.needBackups} />
        <Button variant="outline" onClick={() => go(missing)}>
          {missing === "android" ? t.convert.goAndroid : t.convert.goIphone}
        </Button>
      </>
    )
  }

  const chosen = options?.targets.find((x) => (x.folder ?? MAIN) === target)
  const mediaPath = media === OTHER ? otherMedia.trim() : media === NONE ? null : media
  const needsPassphrase = toAndroid && media === BACKUP && Boolean(options?.encrypted)
  const blocked = toAndroid && options?.android_ready === false
  const canRun =
    Boolean(chosen) && (media === NONE || Boolean(mediaPath)) && (!needsPassphrase || Boolean(passphrase)) && !busy && !blocked

  async function run() {
    if (!chosen) return
    setBusy(true)
    setError(null)
    try {
      await runJob("/api/convert", {
        account_folder: chosen.folder,
        media: mediaPath,
        passphrase: needsPassphrase ? passphrase : null,
      })
      setPassphrase("")
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(false)
  }

  return (
    <>
      <PageHeader title={t.convert.title} lead={toAndroid ? t.convert.leadToAndroid : t.convert.lead} />

      {options === null ? (
        error ? <ErrorNotice message={error} /> : <Busy>{t.common.loading}</Busy>
      ) : (
        <>
          {blocked && (
            <Alert variant="destructive">
              <TriangleAlert />
              <AlertTitle>{t.convert.androidNotWritableTitle}</AlertTitle>
              <AlertDescription className="space-y-2">
                <span className="block">{t.convert.androidNotWritable}</span>
                <Button variant="outline" size="sm" onClick={() => go("android")}>
                  {t.convert.goAndroid}
                </Button>
              </AlertDescription>
            </Alert>
          )}

          <Section n={1} title={toAndroid ? t.convert.sourceTitle : t.convert.targetTitle}>
            <p className="text-sm text-muted-foreground">
              {toAndroid
                ? t.convert.fromIphoneBackup(when(options.backup_checked_at))
                : t.convert.fromBackup(Boolean(options.second_backup), when(options.backup_checked_at))}
            </p>
            <Accounts targets={options.targets} value={target} onChange={setTarget} />
            {!toAndroid && chosen && (chosen.messages ?? 0) > 0 && (
              <Alert>
                <Info />
                <AlertDescription>{t.convert.mergeNote(num(chosen.messages ?? 0))}</AlertDescription>
              </Alert>
            )}
          </Section>

          <Section n={2} title={t.convert.mediaTitle}>
            {toAndroid ? (
              <>
                <RadioGroup value={media} onValueChange={setMedia} aria-label={t.convert.mediaTitle}>
                  <Label htmlFor="media-backup" className={OPTION}>
                    <RadioGroupItem value={BACKUP} id="media-backup" className="mt-0.5" />
                    <span className="grid gap-1">
                      <span className="text-sm font-medium">{t.convert.mediaFromBackup}</span>
                      <span className="text-xs text-muted-foreground">{t.convert.mediaFromBackupNote}</span>
                    </span>
                  </Label>
                  <Label htmlFor="media-none" className={OPTION}>
                    <RadioGroupItem value={NONE} id="media-none" className="mt-0.5" />
                    <span className="grid gap-1">
                      <span className="text-sm font-medium">{t.convert.mediaNone}</span>
                      <span className="text-xs text-muted-foreground">{t.convert.mediaNoneNote}</span>
                    </span>
                  </Label>
                </RadioGroup>
                {needsPassphrase && (
                  <div className="grid gap-2">
                    <Label htmlFor="pass-convert">{t.backup.passLabel}</Label>
                    <Input
                      id="pass-convert"
                      type="password"
                      autoComplete="off"
                      value={passphrase}
                      onChange={(e) => setPassphrase(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">{t.backup.passHint}</p>
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">{t.convert.mediaLead}</p>
                <RadioGroup value={media} onValueChange={setMedia} aria-label={t.convert.mediaTitle}>
                  {(options.media ?? []).map((m) => (
                    <Label key={m.path} htmlFor={`media-${m.path}`} className={OPTION}>
                      <RadioGroupItem value={m.path} id={`media-${m.path}`} className="mt-0.5" />
                      <span className="grid min-w-0 gap-1">
                        <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                          {m.name}
                          {m.suggested && <Badge variant="secondary">{t.convert.suggested}</Badge>}
                        </span>
                        <span className="text-xs text-muted-foreground">{t.convert.mediaFound(m.found, m.sampled)}</span>
                        <Path>{m.path}</Path>
                      </span>
                    </Label>
                  ))}
                  <Label htmlFor="media-other" className={OPTION}>
                    <RadioGroupItem value={OTHER} id="media-other" className="mt-0.5" />
                    <span className="grid w-full min-w-0 gap-2">
                      <span className="text-sm font-medium">{t.convert.mediaOther}</span>
                      {media === OTHER && (
                        <Input
                          aria-label={t.convert.mediaOther}
                          placeholder={t.convert.mediaPlaceholder}
                          value={otherMedia}
                          onChange={(e) => setOtherMedia(e.target.value)}
                        />
                      )}
                    </span>
                  </Label>
                  <Label htmlFor="media-none" className={OPTION}>
                    <RadioGroupItem value={NONE} id="media-none" className="mt-0.5" />
                    <span className="grid gap-1">
                      <span className="text-sm font-medium">{t.convert.mediaNone}</span>
                      <span className="text-xs text-muted-foreground">{t.convert.mediaNoneNote}</span>
                    </span>
                  </Label>
                </RadioGroup>
              </>
            )}
          </Section>

          <div className="space-y-4">
            <ErrorNotice message={error} />
            {busy && <Busy>{t.convert.working}</Busy>}
            <Button variant={state.converted ? "outline" : "default"} disabled={!canRun} onClick={run}>
              {state.converted ? t.convert.again : t.convert.run}
            </Button>
            {state.converted && <ConvertResult entry={state.converted} toAndroid={toAndroid} />}
            {state.converted && <ConversionPreview madeAt={state.converted.made_at} toAndroid={toAndroid} />}
          </div>
        </>
      )}
    </>
  )
}

function Accounts({ targets, value, onChange }: { targets: ConvertTarget[]; value: string; onChange: (v: string) => void }) {
  const { t } = useI18n()
  return (
    <RadioGroup value={value} onValueChange={onChange} aria-label={t.convert.targetTitle}>
      {targets.map((x) => {
        const id = x.folder ?? MAIN
        return (
          <Label key={id} htmlFor={`target-${id}`} className={OPTION}>
            <RadioGroupItem value={id} id={`target-${id}`} className="mt-0.5" />
            <span className="grid min-w-0 gap-1">
              <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                {x.main ? t.convert.mainAccount(x.number_ends) : t.convert.otherAccount(x.number_ends)}
                {x.suggested && <Badge variant="secondary">{t.convert.suggested}</Badge>}
              </span>
              <span className="text-xs text-muted-foreground">{t.convert.hasMessages(num(x.messages ?? 0))}</span>
              {x.folder && <Path>{x.folder}</Path>}
            </span>
          </Label>
        )
      })}
    </RadioGroup>
  )
}

function ConvertResult({ entry, toAndroid }: { entry: ConvertedEntry; toAndroid: boolean }) {
  const { t } = useI18n()
  const r = entry.report
  const converted = Object.values(r.converted).reduce((a, b) => a + b, 0)
  const total = (toAndroid ? r.iphone_messages : r.android_messages) ?? 0
  const skipped = Object.values(r.skipped).reduce((a, b) => a + b, 0)
  // Only what the conversion added counts: WhatsApp's own database can have quirks of its own.
  const before = r.checks_before ?? {}
  const problems = Object.entries(r.checks).filter(
    ([k, v]) => !SUMMARY_CHECKS.has(k) && typeof v === "number" && v > ((before[k] as number | undefined) ?? 0),
  )
  const clean = r.checks.integrity === "ok" && problems.length === 0
  const notes = (r.compatibility ?? []).filter((c) => c.note)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CircleCheck className="size-4 text-primary" />
          {t.convert.doneTitle(num(converted), num(total))}
        </CardTitle>
        <CardDescription>{t.convert.doneLine(when(entry.made_at))}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <StatGrid
          counts={{
            "chats matched": r.chats_matched,
            "chats created": r.chats_created,
            "media placed": r.media_files_copied,
            "media missing": r.media_files_missing,
          }}
        />
        {clean ? (
          <Alert>
            <CircleCheck />
            <AlertDescription>{t.convert.checksClean}</AlertDescription>
          </Alert>
        ) : (
          <Alert variant="destructive">
            <TriangleAlert />
            <AlertTitle>{t.convert.checksFailed}</AlertTitle>
            <AlertDescription>
              {[`integrity: ${String(r.checks.integrity)}`, ...problems.map(([k, v]) => `${k}: ${num(v as number)}`)].join(" · ")}
            </AlertDescription>
          </Alert>
        )}
        {notes.map((c) => (
          <Alert key={c.kind}>
            <Info />
            <AlertTitle>{t.convert.versionTitle(c.kind)}</AlertTitle>
            <AlertDescription>{c.note}</AlertDescription>
          </Alert>
        ))}
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {skipped > 0 && <li>{t.convert.skipped(num(skipped))}</li>}
          {Object.entries(r.not_converted_yet ?? {}).map(([what, n]) => (
            <li key={what}>{t.convert.notYet(capitalized(t.counts[what] ?? what), num(n))}</li>
          ))}
          {toAndroid && <li>{t.convert.notYetToAndroid}</li>}
        </ul>
      </CardContent>
    </Card>
  )
}
