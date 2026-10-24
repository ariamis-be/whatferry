import { useState } from "react"
import { ArrowRight, TriangleAlert } from "lucide-react"

import { api } from "@/api"
import { PageHeader } from "@/components/bits"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { CHECKLIST, type StepProps } from "@/wizard"

export function AccountStep({ overview, refresh, go }: StepProps) {
  const [ticked, setTicked] = useState<Record<string, boolean>>(overview.state.checklist ?? {})
  const allDone = CHECKLIST.every(([key]) => ticked[key])

  async function tick(item: string, done: boolean) {
    setTicked((t) => ({ ...t, [item]: done }))
    try {
      const { checklist } = await api<{ checklist: Record<string, boolean> }>("POST", "/api/checklist", { item, done })
      setTicked(checklist)
      await refresh()
    } catch {
      // The box keeps showing what was clicked.
    }
  }

  return (
    <>
      <PageHeader
        title="Add the Android number on the iPhone"
        lead="WhatsApp sets up the second account itself: its own empty database, folders and keys. Later, only that new account is filled with the Android chats; your current account isn't touched."
      />

      <Card>
        <CardContent className="divide-y">
          {CHECKLIST.map(([key, text]) => (
            <Label key={key} htmlFor={key} className="flex cursor-pointer items-start gap-3 py-3.5 font-normal leading-relaxed first:pt-0 last:pb-0">
              <Checkbox id={key} checked={Boolean(ticked[key])} onCheckedChange={(v) => tick(key, v === true)} className="mt-0.5" />
              <span className="text-sm">{text}</span>
            </Label>
          ))}
        </CardContent>
      </Card>

      <Alert>
        <TriangleAlert />
        <AlertDescription>
          Keep WhatsApp installed on the Android phone until the transfer is finished. If anything goes wrong you can sign
          back in there and your chats are still on it.
        </AlertDescription>
      </Alert>

      <Button size="lg" variant={allDone ? "default" : "outline"} onClick={() => go("after")}>
        {allDone ? "Continue" : "Continue anyway"} <ArrowRight data-icon="inline-end" />
      </Button>
    </>
  )
}
