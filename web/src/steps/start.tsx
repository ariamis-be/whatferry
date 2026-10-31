import { useState } from "react"
import { ArrowRight, Cable, Clock, Lock, Smartphone } from "lucide-react"

import { api } from "@/api"
import { ErrorNotice, Instructions, PageHeader, Section } from "@/components/bits"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { useI18n } from "@/i18n"
import type { Direction, StepProps } from "@/wizard"

const ICONS = [Smartphone, Smartphone, Cable, Clock]

const OPTION =
  "flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-muted/50"

export function StartStep({ overview, refresh }: StepProps) {
  const { t } = useI18n()
  const direction: Direction = overview.state.direction ?? "to-iphone"
  const toAndroid = direction === "to-android"
  const [error, setError] = useState<string | null>(null)

  async function choose(value: string) {
    setError(null)
    try {
      await api("POST", "/api/direction", { direction: value })
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <PageHeader title={toAndroid ? t.start.titleToAndroid : t.start.title} lead={toAndroid ? t.start.leadToAndroid : t.start.lead} />

      <Section title={t.start.directionTitle}>
        <RadioGroup value={direction} onValueChange={choose} aria-label={t.start.directionTitle}
          className="grid gap-2 sm:grid-cols-2">
          {(["to-iphone", "to-android"] as const).map((d) => (
            <Label key={d} htmlFor={`direction-${d}`} className={OPTION}>
              <RadioGroupItem value={d} id={`direction-${d}`} className="mt-0.5" />
              <span className="grid gap-1">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  {d === "to-iphone" ? t.start.android : t.start.iphone}
                  <ArrowRight className="size-3.5" />
                  {d === "to-iphone" ? t.start.iphone : t.start.android}
                </span>
                <span className="text-xs text-muted-foreground">{t.start.directionNote[d]}</span>
              </span>
            </Label>
          ))}
        </RadioGroup>
        <ErrorNotice message={error} />
      </Section>

      <Section title={t.start.needTitle}>
        <ul className="grid gap-2 sm:grid-cols-2">
          {(toAndroid ? t.start.needsToAndroid : t.start.needs).map((text, i) => {
            const Icon = ICONS[i]
            return (
              <li key={i} className="flex gap-3 rounded-lg border p-3 text-sm">
                <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                {text}
              </li>
            )
          })}
        </ul>
      </Section>

      <Section title={t.start.happensTitle}>
        <Instructions items={toAndroid ? t.start.happensToAndroid : t.start.happens} />
      </Section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="size-4" /> {t.start.privateTitle}
          </CardTitle>
          <CardDescription>{t.start.privateLead}</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1.5 pl-5 text-sm">
            {t.start.private(overview.home).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </>
  )
}
