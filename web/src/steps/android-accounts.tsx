import { useState } from "react"
import { Check } from "lucide-react"

import { api, num } from "@/api"
import { ErrorNotice } from "@/components/bits"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useI18n } from "@/i18n"
import type { StepProps } from "@/wizard"

/** The Android accounts checked so far; one is worked on at a time. */
export function AndroidAccounts({ overview, refresh }: Pick<StepProps, "overview" | "refresh">) {
  const { t } = useI18n()
  const accounts = overview.android_accounts
  const [error, setError] = useState<string | null>(null)
  if (accounts.length === 0) return null

  async function select(key: string) {
    setError(null)
    try {
      await api("POST", "/api/android/select", { key })
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.android.accountsTitle}</CardTitle>
        <CardDescription>{t.android.accountsLead}</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {accounts.map((a) => (
            <li
              key={a.key}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 data-[current=true]:border-primary data-[current=true]:bg-muted/50"
              data-current={a.current}
            >
              <span className="grid min-w-0 gap-0.5">
                <span className="text-sm font-medium">{t.android.accountRow(a.number_ends, num(a.messages))}</span>
                <span className="text-xs text-muted-foreground">
                  {t.android.accountProgress(
                    a.destination ? t.android.destinationNames[a.destination] : null,
                    a.second_backup_checked,
                  )}
                </span>
                <span className="font-mono text-xs wrap-anywhere text-muted-foreground">{a.name}</span>
              </span>
              {a.current ? (
                <Badge variant="secondary">
                  <Check data-icon="inline-start" /> {t.android.workingOn}
                </Badge>
              ) : (
                <Button size="sm" variant="outline" onClick={() => select(a.key)}>
                  {t.android.switchTo}
                </Button>
              )}
            </li>
          ))}
        </ul>
        <ErrorNotice message={error} />
      </CardContent>
    </Card>
  )
}
