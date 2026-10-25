import { useEffect, useState } from "react"
import { GitMerge, Info, TriangleAlert } from "lucide-react"

import { api, num, type Destination, type DestinationHint } from "@/api"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { useI18n, type Messages } from "@/i18n"
import type { StepProps } from "@/wizard"

const CHOICES: Destination[] = ["second", "setup", "existing"]

function reason(hint: DestinationHint, t: Messages): string {
  const ends = hint.android_ends ?? "?"
  switch (hint.reason) {
    case "no-whatsapp": return t.destination.reasons.noWhatsapp
    case "number-matches": return t.destination.reasons.matches(ends)
    case "different-number":
      return t.destination.reasons.different(ends, hint.accounts.map((a) => a.number_ends ?? "?").join(", "))
    case "stale-check": return t.destination.reasons.stale
    case "iphone-numbers-unknown": return t.destination.reasons.iphoneUnknown(ends)
    default: return t.destination.reasons.unknown
  }
}

/** Where the Android chats go on the iPhone; asked once the first backup is checked. */
export function DestinationChoice({ overview, refresh }: Pick<StepProps, "overview" | "refresh">) {
  const { t } = useI18n()
  const hint = overview.destination_hint
  const saved = overview.state.destination
  const [choice, setChoice] = useState<Destination | undefined>(saved ?? hint?.suggested)

  // The suggestion counts as chosen until changed, so Continue just works.
  useEffect(() => {
    if (hint && !saved) {
      api("POST", "/api/destination", { choice: hint.suggested }).then(refresh).catch(() => {})
    }
  }, [hint, saved, refresh])

  if (!hint) return null

  async function pick(value: string) {
    setChoice(value as Destination)
    try {
      await api("POST", "/api/destination", { choice: value })
      await refresh()
    } catch {
      // The radio keeps showing what was picked.
    }
  }

  const folders = overview.state.before?.report.account_folders?.length ?? 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.destination.title}</CardTitle>
        <CardDescription>{t.destination.lead}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {hint.accounts.length > 0 && (
          <div className="space-y-1.5">
            <h3 className="text-sm font-medium">{t.destination.accountsTitle}</h3>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {hint.accounts.map((a) => (
                <li key={a.id_ends}>{t.destination.account(a.number_ends, a.country, a.main)}</li>
              ))}
            </ul>
            {folders > 0 && <p className="text-xs text-muted-foreground">{t.destination.folders(folders)}</p>}
          </div>
        )}
        <Alert>
          <Info />
          <AlertDescription>{reason(hint, t)}</AlertDescription>
        </Alert>
        <RadioGroup value={choice} onValueChange={pick} aria-label={t.destination.title}>
          {CHOICES.map((value) => (
            <Label
              key={value}
              htmlFor={`destination-${value}`}
              className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-muted/50"
            >
              <RadioGroupItem value={value} id={`destination-${value}`} className="mt-0.5" />
              <span className="grid gap-1">
                <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                  {t.destination.options[value].title}
                  {value === hint.suggested && <Badge variant="secondary">{t.destination.suggested}</Badge>}
                </span>
                <span className="text-xs text-muted-foreground">{t.destination.options[value].body}</span>
              </span>
            </Label>
          ))}
        </RadioGroup>
        {choice === "second" && hint.full && (
          <Alert>
            <TriangleAlert />
            <AlertDescription>{t.destination.full}</AlertDescription>
          </Alert>
        )}
        {choice === "existing" && hint.messages ? (
          <Alert>
            <GitMerge />
            <AlertDescription>{t.destination.merge(num(hint.messages))}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  )
}
