import { useState } from "react"
import { CircleCheck, TriangleAlert } from "lucide-react"

import { num, runJob, size, when, type WrittenEntry } from "@/api"
import { Busy, ErrorNotice, PageHeader, Path, Section } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useI18n } from "@/i18n"
import type { StepProps } from "@/wizard"

export function WriteStep({ overview, refresh, go }: StepProps) {
  const { t } = useI18n()
  const state = overview.state
  const converted = state.converted
  const [passphrase, setPassphrase] = useState("")
  const [skipCheck, setSkipCheck] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!converted) {
    return (
      <>
        <PageHeader title={t.write.title} lead={t.write.needConvert} />
        <Button variant="outline" onClick={() => go("convert")}>
          {t.write.goConvert}
        </Button>
      </>
    )
  }

  // The backup the conversion came from, as the wizard checked it.
  const source = [state.after, state.before].find((e) => e?.folder === converted.backup)
  const encrypted = source?.report.device.encrypted ?? true

  async function write() {
    setBusy(true)
    setError(null)
    try {
      await runJob("/api/write", { passphrase: encrypted ? passphrase : null, skip_source_check: skipCheck })
      setPassphrase("")
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(false)
  }

  return (
    <>
      <PageHeader title={t.write.title} lead={t.write.lead} />

      <Section n={1} title={t.write.fromTitle}>
        <p className="text-sm">{t.write.from(source ? when(source.report.device.backup_date) : "?")}</p>
        <Path>{converted.backup}</Path>
        <p className="text-sm text-muted-foreground">{t.write.untouched}</p>
      </Section>

      <Section n={2} title={t.write.passTitle}>
        {encrypted ? (
          <div className="grid gap-2">
            <Label htmlFor="pass-write">{t.backup.passLabel}</Label>
            <Input
              id="pass-write"
              type="password"
              autoComplete="off"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t.backup.passHint}</p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t.write.noPass}</p>
        )}
        <Label htmlFor="skip-check" className="flex items-start gap-3 font-normal">
          <Checkbox
            id="skip-check"
            checked={skipCheck}
            onCheckedChange={(v) => setSkipCheck(v === true)}
            className="mt-0.5"
          />
          <span className="grid gap-1">
            <span className="text-sm">{t.write.skipLabel}</span>
            <span className="text-xs text-muted-foreground">{t.write.skipNote}</span>
          </span>
        </Label>
      </Section>

      <div className="space-y-4">
        <ErrorNotice message={error} />
        {error?.includes("isn't the one the conversion was made") && (
          <Alert>
            <TriangleAlert />
            <AlertTitle>{t.write.changedTitle}</AlertTitle>
            <AlertDescription>{t.write.changedBody}</AlertDescription>
          </Alert>
        )}
        {busy && <Busy>{t.write.working}</Busy>}
        <Button
          variant={state.written ? "outline" : "default"}
          disabled={busy || (encrypted && !passphrase)}
          onClick={write}
        >
          {state.written ? t.write.again : t.write.run}
        </Button>
        {state.written && <WriteResult entry={state.written} />}
      </div>
    </>
  )
}

function WriteResult({ entry }: { entry: WrittenEntry }) {
  const { t } = useI18n()
  const r = entry.report
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <CircleCheck className="size-4 text-primary" />
          {t.write.doneTitle}
          {!r.source_checked && <Badge variant="destructive">{t.write.unchecked}</Badge>}
        </CardTitle>
        <CardDescription>{t.write.doneLine(when(entry.made_at))}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Path>{entry.folder}</Path>
        <p className="text-sm">{t.write.added(num(r.added_files), size(r.added_bytes), num(r.verified_files))}</p>
      </CardContent>
    </Card>
  )
}
