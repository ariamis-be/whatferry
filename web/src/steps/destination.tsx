import { useEffect, useRef, useState } from "react"
import { GitMerge, Info, TriangleAlert } from "lucide-react"

import { api, num, type Destination, type DestinationHint } from "@/api"
import { ErrorNotice } from "@/components/bits"
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
    case "second-started": return t.destination.reasons.secondStarted(ends)
    default: return t.destination.reasons.unknown
  }
}

function numbers(hint: DestinationHint): string {
  return hint.accounts.map((a) => a.number_ends ?? "?").join(", ") || "?"
}

/** Picking "existing" by hand, or when the numbers match: what it means here. */
function ExistingWarnings({ hint }: { hint: DestinationHint }) {
  const { t } = useI18n()
  const started = hint.reason === "second-started"
  const matched = hint.reason === "number-matches" || started
  // Without a match the chats would land in the main account, so a merge
  // is with its messages; a started second account has none to merge with.
  const messages = started ? null : matched ? hint.messages : hint.main_messages
  return (
    <>
      {started && (
        <Alert>
          <Info />
          <AlertDescription>{t.destination.secondNoChats}</AlertDescription>
        </Alert>
      )}
      {!matched && !hint.stale && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertDescription>
            {hint.android_ends && hint.accounts.some((a) => a.number_ends)
              ? t.destination.notMatching(hint.android_ends, numbers(hint))
              : t.destination.cantConfirm}
          </AlertDescription>
        </Alert>
      )}
      {messages ? (
        <Alert>
          <GitMerge />
          <AlertDescription>{t.destination.merge(num(messages))}</AlertDescription>
        </Alert>
      ) : null}
    </>
  )
}

/** Where the Android chats go on the iPhone; asked once the first backup is checked. */
export function DestinationChoice({ overview, refresh }: Pick<StepProps, "overview" | "refresh">) {
  const { t } = useI18n()
  const hint = overview.destination_hint
  const saved = overview.state.destination
  // What was clicked, until the server has it: then what it saved, else the suggestion.
  const [picked, setPicked] = useState<Destination | undefined>()
  const [error, setError] = useState<string | null>(null)
  const choice = picked ?? saved ?? hint?.suggested
  const pickedRef = useRef(false)

  // The suggestion counts as chosen until changed, so Continue just works;
  // never over a choice made meanwhile.
  useEffect(() => {
    if (hint && !saved && !pickedRef.current) {
      api("POST", "/api/destination", { choice: hint.suggested }).then(refresh).catch(() => {})
    }
  }, [hint, saved, refresh])

  if (!hint) return null

  async function pick(value: string) {
    pickedRef.current = true
    setPicked(value as Destination)
    setError(null)
    try {
      await api("POST", "/api/destination", { choice: value })
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
    // Back to what the server holds: the new choice once saved, the old one if not.
    setPicked(undefined)
  }

  // Folders already tied to a known account are shown with it, not again.
  const linked = new Set(hint.accounts.map((a) => a.folder))
  const folders = overview.state.before?.report.account_folders?.filter((f) => !linked.has(f.folder)).length ?? 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.destination.title}</CardTitle>
        <CardDescription>{t.destination.lead}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {hint.accounts.length > 0 && !hint.stale && (
          <div className="space-y-1.5">
            <h3 className="text-sm font-medium">{t.destination.accountsTitle}</h3>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {hint.accounts.map((a) => (
                <li key={`${a.number_ends}-${a.id_ends}`}>{t.destination.account(a.number_ends, a.country, a.main, a.has_chats ?? a.main)}</li>
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
        <ErrorNotice message={error} />
        {choice === "second" && hint.full && (
          <Alert>
            <TriangleAlert />
            <AlertDescription>{t.destination.full}</AlertDescription>
          </Alert>
        )}
        {choice === "existing" && <ExistingWarnings hint={hint} />}
        {choice === "setup" && hint.has_whatsapp && !hint.stale && (
          <Alert variant="destructive">
            <TriangleAlert />
            <AlertDescription>
              {t.destination.replaceExisting(hint.accounts.some((a) => a.number_ends) ? numbers(hint) : null)}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
