import { useCallback, useEffect, useState, type ReactNode } from "react"
import { CircleCheck, CircleX, RefreshCw, Smartphone, TriangleAlert } from "lucide-react"

import { api, runJob, when, type RestoreStatus } from "@/api"
import { Busy, ErrorNotice, Instructions, PageHeader, Section } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useI18n } from "@/i18n"
import { AndroidCopyStep } from "@/steps/android-copy"
import type { StepProps } from "@/wizard"

/** iOS names have a curly ’ ("Anna’s iPhone") most keyboards don't type: ' counts the same, as does case. */
function sameName(typed: string, name: string) {
  const plain = (s: string) => s.normalize("NFKC").replace(/[‘’]/g, "'").trim().toLowerCase()
  return plain(typed) === plain(name)
}

function findPhone(): Promise<RestoreStatus> {
  return api<RestoreStatus>("GET", "/api/restore/status").catch((e: Error) => ({
    phones: [],
    error: e.message,
    udid: null,
  }))
}

/** Onto the phone: an iPhone restore, or for iPhone -> Android a copy onto the Android phone. */
export function RestoreStep(props: StepProps) {
  const { t } = useI18n()
  const state = props.overview.state
  if (state.direction !== "to-android") return <IphoneRestoreStep {...props} />
  if (state.written) return <AndroidCopyStep {...props} />
  return (
    <>
      <PageHeader title={t.copy.title} lead={t.restore.needWrite} />
      <Button variant="outline" onClick={() => props.go("write")}>
        {t.restore.goWrite}
      </Button>
    </>
  )
}

function IphoneRestoreStep({ overview, refresh, go }: StepProps) {
  const { t } = useI18n()
  const state = overview.state
  const written = state.written
  const [status, setStatus] = useState<RestoreStatus | null>(null)
  const [passphrase, setPassphrase] = useState("")
  const [typed, setTyped] = useState("")
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const hasWritten = Boolean(written)
  useEffect(() => {
    if (!hasWritten) return
    let live = true
    findPhone().then((found) => live && setStatus(found))
    return () => {
      live = false
    }
  }, [hasWritten])

  const look = useCallback(() => {
    setStatus(null)
    findPhone().then(setStatus)
  }, [])

  if (!written) {
    return (
      <>
        <PageHeader title={t.restore.title} lead={t.restore.needWrite} />
        <Button variant="outline" onClick={() => go("write")}>
          {t.restore.goWrite}
        </Button>
      </>
    )
  }

  // The backup the new one was copied from, as the wizard checked it: its
  // date is the moment the phone goes back to.
  const source = [state.after, state.before].find((e) => e?.folder === written.from)
  const backupDate = source ? when(source.report.device.backup_date) : "?"
  const encrypted = source?.report.device.encrypted ?? true
  const phone = status?.phones.find((p) => p.udid.toUpperCase() === status.udid?.toUpperCase())
  // Typed to confirm: the name the phone shows in Settings, else the end of its ID.
  const name = phone ? (phone.name || phone.udid.slice(-6)) : ""
  const phoneReady = Boolean(phone?.paired && phone.find_my === false)
  const busy = progress !== null
  const canRestore = phoneReady && name !== "" && sameName(typed, name) && (!encrypted || Boolean(passphrase)) && !busy

  async function run() {
    setProgress(0)
    setError(null)
    try {
      await runJob("/api/restore", { passphrase: encrypted ? passphrase : null, confirmed: true }, setProgress)
      setPassphrase("")
      setTyped("")
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
    setProgress(null)
  }

  return (
    <>
      <PageHeader title={t.restore.title} lead={t.restore.lead} />

      <Alert variant="destructive">
        <TriangleAlert />
        <AlertTitle>{t.restore.warnTitle}</AlertTitle>
        <AlertDescription>{t.restore.warnBody(backupDate)}</AlertDescription>
      </Alert>

      <Section n={1} title={t.restore.beforeTitle}>
        <Instructions items={t.restore.before} />
      </Section>

      <Section n={2} title={t.restore.phoneTitle}>
        {status === null ? (
          <Busy>{t.restore.looking}</Busy>
        ) : status.error ? (
          <ErrorNotice message={status.error} />
        ) : !phone ? (
          <Alert>
            <Smartphone />
            <AlertTitle>{t.restore.noPhone}</AlertTitle>
            <AlertDescription>{t.restore.noPhoneBody(status.phones.length)}</AlertDescription>
          </Alert>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Smartphone className="size-4" />
                {phone.name ?? t.backup.iphone}
              </CardTitle>
              <CardDescription>{t.restore.phoneLine(phone.ios_version ?? "?")}</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1.5 text-sm">
                <Check ok={true}>{t.restore.matches}</Check>
                <Check ok={phone.paired}>{phone.paired ? t.restore.trusted : t.restore.notTrusted}</Check>
                <Check ok={phone.find_my === false}>
                  {phone.find_my === false
                    ? t.restore.findMyOff
                    : phone.find_my
                      ? t.restore.findMyOn
                      : t.restore.findMyUnknown}
                </Check>
              </ul>
            </CardContent>
          </Card>
        )}
        <Button variant="ghost" onClick={look} disabled={busy}>
          <RefreshCw data-icon="inline-start" /> {t.restore.lookAgain}
        </Button>
      </Section>

      <Section n={3} title={t.restore.confirmTitle}>
        {encrypted && (
          <div className="grid gap-2">
            <Label htmlFor="pass-restore">{t.backup.passLabel}</Label>
            <Input
              id="pass-restore"
              type="password"
              autoComplete="off"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
            />
          </div>
        )}
        {phone && (
          <div className="grid gap-2">
            <Label htmlFor="confirm-restore">{t.restore.typeName(name)}</Label>
            <Input
              id="confirm-restore"
              autoComplete="off"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
          </div>
        )}
      </Section>

      <div className="space-y-4">
        <ErrorNotice message={error} />
        {busy && (
          <div className="space-y-2" role="status">
            <Busy>{t.restore.working(progress ?? 0)}</Busy>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full bg-primary transition-[width]" style={{ width: `${progress ?? 0}%` }} />
            </div>
            <p className="text-xs text-muted-foreground">{t.restore.keepConnected}</p>
          </div>
        )}
        <Button variant="destructive" disabled={!canRestore} onClick={run}>
          {t.restore.run}
        </Button>
        {state.restored && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CircleCheck className="size-4 text-primary" />
                {t.restore.doneTitle}
              </CardTitle>
              <CardDescription>{t.restore.doneLine(when(state.restored.restored_at))}</CardDescription>
            </CardHeader>
            <CardContent>
              <Instructions items={t.restore.after} />
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}

function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      {ok ? (
        <CircleCheck className="mt-0.5 size-4 shrink-0 text-primary" />
      ) : (
        <CircleX className="mt-0.5 size-4 shrink-0 text-destructive" />
      )}
      {children}
    </li>
  )
}
