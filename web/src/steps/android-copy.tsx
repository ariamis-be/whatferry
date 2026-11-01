import { useCallback, useEffect, useState } from "react"
import { CircleCheck, RefreshCw, Smartphone, TriangleAlert } from "lucide-react"

import { api, num, runJob, when, type AndroidPhones } from "@/api"
import { Busy, Disclosure, ErrorNotice, Instructions, PageHeader, Path, Section } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { useI18n } from "@/i18n"
import type { StepProps } from "@/wizard"

const OPTION =
  "flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-muted/50"

function findPhones(): Promise<AndroidPhones> {
  return api<AndroidPhones>("GET", "/api/restore/status").catch((e: Error) => ({
    direction: "to-android" as const,
    adb: null,
    devices: [],
    error: e.message,
    suggested_folder: "",
  }))
}

/** iPhone -> Android: the written WhatsApp folder copied onto the phone, then WhatsApp's own restore. */
export function AndroidCopyStep({ overview, refresh }: StepProps) {
  const { t } = useI18n()
  const state = overview.state
  const written = state.written
  const [status, setStatus] = useState<AndroidPhones | null>(null)
  const [serial, setSerial] = useState("")
  const [folder, setFolder] = useState("")
  const [cleared, setCleared] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const show = useCallback((found: AndroidPhones) => {
    setStatus(found)
    const ready = found.devices.filter((d) => d.ready)
    const phone = ready.length === 1 ? ready[0] : undefined
    setSerial((s) => s || phone?.serial || "")
  }, [])

  useEffect(() => {
    let live = true
    findPhones().then((found) => live && show(found))
    return () => {
      live = false
    }
  }, [show])

  function look() {
    setStatus(null)
    findPhones().then(show)
  }

  if (!written) return null
  const phone = status?.devices.find((d) => d.serial === serial)
  // Only ever one of this phone's own folders: a choice made for another phone doesn't carry over.
  const folders = phone?.folders ?? []
  const target = folders.includes(folder)
    ? folder
    : folders.includes(status?.suggested_folder ?? "")
      ? (status?.suggested_folder ?? "")
      : (folders[0] ?? "")

  async function copy() {
    setBusy(true)
    setError(null)
    try {
      await runJob("/api/restore", { confirmed: true, serial, folder: target })
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(false)
  }

  return (
    <>
      <PageHeader title={t.copy.title} lead={t.copy.lead} />

      <Alert variant="destructive">
        <TriangleAlert />
        <AlertTitle>{t.copy.warnTitle}</AlertTitle>
        <AlertDescription>{t.copy.warnBody}</AlertDescription>
      </Alert>

      <Section n={1} title={t.copy.beforeTitle}>
        <Instructions items={t.copy.before} />
      </Section>

      <Section n={2} title={t.copy.phoneTitle}>
        {status === null ? (
          <Busy>{t.copy.looking}</Busy>
        ) : !status.adb ? (
          <Alert>
            <Smartphone />
            <AlertTitle>{t.copy.noAdbTitle}</AlertTitle>
            <AlertDescription>{t.copy.noAdb}</AlertDescription>
          </Alert>
        ) : status.devices.length === 0 ? (
          <Alert>
            <Smartphone />
            <AlertTitle>{t.copy.noPhoneTitle}</AlertTitle>
            <AlertDescription>{t.copy.noPhone}</AlertDescription>
          </Alert>
        ) : (
          <RadioGroup value={serial} onValueChange={setSerial} aria-label={t.copy.phoneTitle}>
            {status.devices.map((d) => (
              <Label key={d.serial} htmlFor={`phone-${d.serial}`} className={OPTION}>
                <RadioGroupItem value={d.serial} id={`phone-${d.serial}`} disabled={!d.ready} className="mt-0.5" />
                <span className="grid gap-1">
                  <span className="text-sm font-medium">{d.model ?? d.serial}</span>
                  <span className="text-xs text-muted-foreground">{d.ready ? t.copy.ready : d.advice}</span>
                </span>
              </Label>
            ))}
          </RadioGroup>
        )}
        <ErrorNotice message={status?.error ?? phone?.error} />
        {folders.length > 1 && (
          <div className="space-y-2">
            <p className="text-sm">{t.copy.whichFolder}</p>
            <RadioGroup value={target} onValueChange={setFolder} aria-label={t.copy.whichFolder}>
              {folders.map((f) => (
                <Label key={f} htmlFor={`folder-${f}`} className={OPTION}>
                  <RadioGroupItem value={f} id={`folder-${f}`} className="mt-0.5" />
                  <Path className="text-foreground">{f}</Path>
                </Label>
              ))}
            </RadioGroup>
          </div>
        )}
        <Button variant="ghost" onClick={look} disabled={busy}>
          <RefreshCw data-icon="inline-start" /> {t.copy.lookAgain}
        </Button>
      </Section>

      <Section n={3} title={t.copy.confirmTitle}>
        <Label htmlFor="cleared" className="flex items-start gap-3 font-normal">
          <Checkbox id="cleared" checked={cleared} onCheckedChange={(v) => setCleared(v === true)} className="mt-0.5" />
          <span className="text-sm">{t.copy.cleared}</span>
        </Label>
      </Section>

      <div className="space-y-4">
        <ErrorNotice message={error} />
        {busy && <Busy>{t.copy.working}</Busy>}
        <Button disabled={!phone?.ready || !target || !cleared || busy} onClick={copy}>
          {state.restored ? t.copy.again : t.copy.run}
        </Button>
        {state.restored && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CircleCheck className="size-4 text-primary" />
                {t.copy.doneTitle}
              </CardTitle>
              <CardDescription>
                {t.copy.doneLine(when(state.restored.restored_at), num(state.restored.media_files ?? 0))}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {state.restored.kept && <p className="text-sm text-muted-foreground">{t.copy.kept(state.restored.kept)}</p>}
              <Instructions items={t.copy.after} />
            </CardContent>
          </Card>
        )}
        <Disclosure title={t.copy.manualTitle}>
          <div className="space-y-2 text-sm">
            <p>{t.copy.manual}</p>
            <Path className="block">{written.folder}</Path>
            <p>{t.copy.manualInto}</p>
            <Path className="block">Android/media/com.whatsapp/WhatsApp</Path>
          </div>
        </Disclosure>
      </div>
    </>
  )
}
