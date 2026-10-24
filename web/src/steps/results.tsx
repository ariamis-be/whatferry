import { useEffect, useState } from "react"
import { Check, Copy, RotateCcw } from "lucide-react"

import { api } from "@/api"
import { Code, PageHeader, Section } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import type { StepProps } from "@/wizard"

export function ResultsStep({ overview, refresh, go }: StepProps) {
  const [text, setText] = useState("Loading…")
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    api<{ text: string }>("GET", "/api/summary")
      .then((s) => setText(s.text))
      .catch((e: Error) => setText(e.message))
  }, [])

  async function copy() {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function startOver() {
    if (!confirm("Forget all progress? Decrypted copies stay on disk until you delete them.")) return
    await api("POST", "/api/reset", {})
    await refresh()
    go("start")
  }

  return (
    <>
      <PageHeader
        title="Results"
        lead="This summary holds counts, versions and file locations: no messages, names or phone numbers. Send it on so the transfer can be built for this exact setup."
      />

      <div className="space-y-3">
        <Textarea readOnly aria-label="Summary" value={text} className="min-h-96 font-mono text-xs leading-relaxed" />
        <div className="flex items-center gap-3">
          <Button size="lg" onClick={copy}>
            {copied ? <Check data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
            {copied ? "Copied" : "Copy summary"}
          </Button>
        </div>
      </div>

      <Section title="What happens next">
        <p className="text-sm">
          The step that writes the Android chats into the new account isn't built yet. These results are what it will
          be built from.
        </p>
      </Section>

      <Section title="Cleaning up">
        <p className="text-sm">
          Decrypted copies are in <Code>{overview.home}</Code>. Delete that folder whenever you like; the summary above
          doesn't need it.
        </p>
        <Button variant="outline" onClick={startOver}>
          <RotateCcw data-icon="inline-start" /> Start over
        </Button>
      </Section>
    </>
  )
}
