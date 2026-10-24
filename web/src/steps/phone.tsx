import { useCallback, useEffect, useState } from "react"
import { CircleCheck, Download, Smartphone, TriangleAlert, Usb } from "lucide-react"

import { api, runJob, size, when, type Candidate, type Phone, type PhoneBackup, type PhoneStatus } from "@/api"
import { Busy, Disclosure, ErrorNotice, Instructions, Path } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useI18n, type Messages } from "@/i18n"
import type { Platform } from "@/wizard"

function fetchStatus(): Promise<PhoneStatus | Error> {
  return api<PhoneStatus>("GET", "/api/android/phone").catch((e: Error) => e)
}

// The server explains unusable files in English; the page says it in the
// page's language, from the same facts.
function note(b: PhoneBackup, t: Messages): string | null {
  if (b.name.includes("increment")) return t.phone.notes.increment
  if (b.kind === "crypt14" || b.kind === "crypt12") return t.phone.notes.rooted
  if (b.kind === "other") return t.phone.notes.other
  return null
}

function advice(p: Phone, t: Messages): string {
  return t.phone.advice[p.state] ?? t.phone.otherState(p.state)
}

/** Copy a backup straight off a phone plugged in with USB debugging. */
export function PhoneCopy({ platform, folder, onCopied }: {
  platform: Platform
  folder: string
  onCopied: (file: Candidate) => void
}) {
  const { t } = useI18n()
  const [status, setStatus] = useState<PhoneStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copying, setCopying] = useState<string | null>(null)
  const [copied, setCopied] = useState<Candidate | null>(null)

  const show = useCallback((s: PhoneStatus | Error) => {
    if (s instanceof Error) setError(s.message)
    else setStatus(s)
  }, [])

  useEffect(() => {
    let live = true
    fetchStatus().then((s) => live && show(s))
    return () => {
      live = false
    }
  }, [show])

  function look() {
    setStatus(null)
    setError(null)
    fetchStatus().then(show)
  }

  async function copy(serial: string, path: string) {
    setCopying(path)
    setError(null)
    try {
      const file = await runJob<Candidate>("/api/android/phone/pull", { serial, path })
      setCopied(file)
      onCopied(file)
    } catch (e) {
      setError((e as Error).message)
    }
    setCopying(null)
  }

  const phones = status?.devices ?? []
  const ready = phones.filter((p) => p.ready)

  const row = (serial: string, b: PhoneBackup) => (
    <li key={b.path} className="flex flex-wrap items-start justify-between gap-3 rounded-md bg-muted/50 p-3">
      <span className="grid min-w-0 gap-1">
        <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
          {b.name}
          <Badge variant="outline">{t.phone.account(b.app, b.account)}</Badge>
        </span>
        <span className="text-xs text-muted-foreground">
          {size(b.size)} · {when(b.modified)}
        </span>
        <Path>{b.path}</Path>
        {note(b, t) && <span className="text-xs text-muted-foreground">{note(b, t)}</span>}
      </span>
      {b.usable && (
        <Button size="sm" disabled={copying !== null} onClick={() => copy(serial, b.path)}>
          <Download data-icon="inline-start" />
          {copying === b.path ? t.phone.copying : t.phone.copy}
        </Button>
      )}
    </li>
  )

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t.phone.intro(folder)}</p>

      {status === null && !error && <Busy>{t.phone.looking}</Busy>}
      <ErrorNotice message={error ?? status?.error} />

      {status && !status.adb && (
        <Alert>
          <TriangleAlert />
          <AlertTitle>{t.phone.noAdbTitle}</AlertTitle>
          <AlertDescription className="space-y-2">
            <span className="block">{t.phone.noAdbIntro}</span>
            <Instructions items={t.phone.install[platform]} />
            <span className="block">{t.phone.download}</span>
          </AlertDescription>
        </Alert>
      )}

      {status?.adb && ready.length === 0 && (
        <div className="space-y-3 rounded-lg border p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium">
            <Usb className="size-4" /> {t.phone.debugTitle}
          </h3>
          <Instructions items={t.phone.debug} />
          <p className="text-xs text-muted-foreground">{t.phone.debugOff}</p>
        </div>
      )}

      {phones
        .filter((p) => !p.ready)
        .map((p) => (
          <Alert key={p.serial}>
            <Smartphone />
            <AlertTitle>{t.phone.notReady(p.model ?? t.phone.phone)}</AlertTitle>
            <AlertDescription>{advice(p, t)}</AlertDescription>
          </Alert>
        ))}

      {ready.map((phone) => {
        const backups = phone.backups ?? []
        const usable = backups.filter((b) => b.usable)
        const other = backups.filter((b) => !b.usable)
        return (
          <div key={phone.serial} className="space-y-3 rounded-lg border p-4">
            <h3 className="flex items-center gap-2 text-sm font-medium">
              <Smartphone className="size-4" /> {phone.model ?? t.phone.phone}
              <Badge variant="secondary">{t.phone.connected}</Badge>
            </h3>
            <ErrorNotice message={phone.error} />
            {backups.length === 0 && <p className="text-sm text-muted-foreground">{t.phone.noBackups}</p>}
            {backups.length > 0 && usable.length === 0 && (
              <p className="text-sm text-muted-foreground">{t.phone.noUsable}</p>
            )}
            {usable.length > 0 && <ul className="space-y-2">{usable.map((b) => row(phone.serial, b))}</ul>}
            {other.length > 0 && (
              <Disclosure title={t.phone.otherFiles(other.length)}>
                <ul className="space-y-2">{other.map((b) => row(phone.serial, b))}</ul>
              </Disclosure>
            )}
          </div>
        )
      })}

      {copied && (
        <Alert>
          <CircleCheck />
          <AlertTitle>{t.phone.copiedTitle(copied.name)}</AlertTitle>
          <AlertDescription>
            {t.phone.copiedBody} <Path>{copied.path}</Path>
          </AlertDescription>
        </Alert>
      )}

      {(status || error) && (
        <Button variant="outline" onClick={look}>
          <Usb data-icon="inline-start" /> {t.phone.findPhone}
        </Button>
      )}
    </div>
  )
}
