import { Cable, Clock, Lock, Smartphone } from "lucide-react"

import { Instructions, PageHeader, Section } from "@/components/bits"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useI18n } from "@/i18n"
import type { StepProps } from "@/wizard"

const ICONS = [Smartphone, Smartphone, Cable, Clock]

export function StartStep({ overview }: StepProps) {
  const { t } = useI18n()
  return (
    <>
      <PageHeader title={t.start.title} lead={t.start.lead} />

      <Section title={t.start.needTitle}>
        <ul className="grid gap-2 sm:grid-cols-2">
          {t.start.needs.map((text, i) => {
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
        <Instructions items={t.start.happens} />
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
