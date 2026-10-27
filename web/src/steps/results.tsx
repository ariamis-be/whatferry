import { useEffect, useState } from "react"
import { Check, Copy, RotateCcw } from "lucide-react"

import { api } from "@/api"
import { Disclosure, PageHeader, Section } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useI18n } from "@/i18n"
import type { StepProps } from "@/wizard"

export function ResultsStep({ overview, refresh, go }: StepProps) {
  const { t } = useI18n()
  const [text, setText] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let live = true
    api<{ text: string }>("GET", "/api/summary")
      .then((s) => live && setText(s.text))
      .catch((e: Error) => live && setText(e.message))
    return () => {
      live = false
    }
  }, [])

  async function copy() {
    await navigator.clipboard.writeText(text ?? "")
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function startOver() {
    if (!confirm(t.results.confirmReset)) return
    await api("POST", "/api/reset", {})
    await refresh()
    go("start")
  }

  return (
    <>
      <PageHeader title={t.results.title} lead={t.results.lead} />

      <div className="space-y-3">
        {t.results.summaryLanguage && <p className="text-xs text-muted-foreground">{t.results.summaryLanguage}</p>}
        {/* Folded: Copy is all most people need. Unwrapped: paths stay on one line. */}
        <Disclosure title={t.results.summaryLabel}>
          <Textarea
            readOnly
            wrap="off"
            aria-label={t.results.summaryLabel}
            value={text ?? t.common.loading}
            lang="en"
            className="min-h-96 overflow-x-auto font-mono text-xs leading-relaxed whitespace-pre"
          />
        </Disclosure>
        <Button onClick={copy} disabled={text === null}>
          {copied ? <Check data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
          {copied ? t.results.copied : t.results.copy}
        </Button>
      </div>

      <Section title={t.results.nextTitle}>
        <p className="text-sm">{t.results.next}</p>
      </Section>

      <Section title={t.results.cleanTitle}>
        <p className="text-sm">{t.results.clean(overview.home)}</p>
        <Button variant="outline" onClick={startOver}>
          <RotateCcw data-icon="inline-start" /> {t.results.startOver}
        </Button>
      </Section>
    </>
  )
}
