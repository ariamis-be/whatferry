import { useState } from "react"
import { TriangleAlert } from "lucide-react"

import { api } from "@/api"
import { PageHeader } from "@/components/bits"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { useI18n } from "@/i18n"
import { CHECKLIST, type StepProps } from "@/wizard"

export function AccountStep({ overview, refresh }: StepProps) {
  const { t } = useI18n()
  const [ticked, setTicked] = useState<Record<string, boolean>>(overview.state.checklist ?? {})

  async function tick(item: string, done: boolean) {
    setTicked((current) => ({ ...current, [item]: done }))
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
      <PageHeader title={t.account.title} lead={t.account.lead} />

      <Card>
        <CardContent className="divide-y">
          {CHECKLIST.map((key) => (
            <Label
              key={key}
              htmlFor={key}
              className="flex cursor-pointer items-start gap-3 py-3.5 font-normal leading-relaxed first:pt-0 last:pb-0"
            >
              <Checkbox
                id={key}
                checked={Boolean(ticked[key])}
                onCheckedChange={(v) => tick(key, v === true)}
                className="mt-0.5"
              />
              <span className="text-sm">{t.account.checklist[key]}</span>
            </Label>
          ))}
        </CardContent>
      </Card>

      <Alert>
        <TriangleAlert />
        <AlertDescription>{t.account.keepAndroid}</AlertDescription>
      </Alert>
    </>
  )
}
