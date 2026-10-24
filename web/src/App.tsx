import { useCallback, useEffect, useState } from "react"
import { Check, ShieldCheck } from "lucide-react"

import { api, TOKEN, type Overview, type State } from "@/api"
import { ErrorNotice } from "@/components/bits"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import { AccountStep } from "@/steps/account"
import { AndroidStep } from "@/steps/android"
import { BackupStep } from "@/steps/backup"
import { ResultsStep } from "@/steps/results"
import { StartStep } from "@/steps/start"
import { CHECKLIST, STEPS, type StepId } from "@/wizard"

function isDone(id: StepId, s: State) {
  switch (id) {
    case "start": return Boolean(s.android || s.before)
    case "android": return Boolean(s.android)
    case "before": return Boolean(s.before)
    case "account": return CHECKLIST.every(([key]) => s.checklist?.[key])
    case "after": return Boolean(s.after)
    default: return false
  }
}

export default function App() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(TOKEN ? null : "Open the wizard with the link `whatferry ui` printed.")
  const [current, setCurrent] = useState<StepId>("start")

  const refresh = useCallback(async () => {
    setOverview(await api<Overview>("GET", "/api/overview"))
  }, [])

  useEffect(() => {
    if (!TOKEN) return
    api<Overview>("GET", "/api/overview")
      .then((o) => {
        setOverview(o)
        const saved = STEPS.find((s) => s.id === o.state.step)
        if (saved) setCurrent(saved.id)
      })
      .catch((e: Error) => setError(`Can't reach whatferry: ${e.message}. Is \`whatferry ui\` still running?`))
  }, [])

  const go = useCallback((step: StepId) => {
    setCurrent(step)
    window.scrollTo(0, 0)
    document.getElementById("main")?.focus()
    api("POST", "/api/step", { step }).catch(() => {})
  }, [])

  const state = overview?.state ?? {}
  const index = STEPS.findIndex((s) => s.id === current)
  const props = overview ? { overview, refresh, go } : null

  return (
    <div className="min-h-svh">
      <header className="sticky top-0 z-10 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <div className="flex h-14 items-center justify-between gap-4">
            <div className="flex items-center gap-2.5 font-semibold">
              <img src="/static/icon.svg" alt="" className="size-6" />
              whatferry
            </div>
            <p className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
              <ShieldCheck className="size-3.5" />
              Stays on this computer · never writes to either phone
            </p>
          </div>
          <nav aria-label="Steps" className="pb-3">
            <ol className="flex gap-1.5">
              {STEPS.map((step, i) => {
                const done = isDone(step.id, state)
                const active = step.id === current
                return (
                  <li key={step.id} className={cn("min-w-0 flex-1", active && "max-sm:flex-[3]")}>
                    <button
                      type="button"
                      onClick={() => go(step.id)}
                      aria-current={active ? "step" : undefined}
                      aria-label={`Step ${i + 1}: ${step.title}${done ? " (done)" : ""}`}
                      className="group flex w-full flex-col gap-2 rounded-sm py-1 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                    >
                      <span
                        className={cn(
                          "h-1 rounded-full bg-border transition-colors",
                          (done || active) && "bg-primary",
                          active && !done && "bg-primary/60",
                        )}
                      />
                      <span
                        aria-hidden
                        className={cn(
                          "flex items-center gap-1 truncate text-xs text-muted-foreground group-hover:text-foreground",
                          active && "font-medium text-foreground",
                        )}
                      >
                        {done ? <Check className="size-3 shrink-0" /> : <span className="tabular-nums">{i + 1}</span>}
                        <span className={cn("truncate", !active && "max-sm:hidden")}>{step.title}</span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ol>
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-10 outline-none sm:px-6 sm:py-14">
        {error && <ErrorNotice message={error} />}
        {!error && !props && (
          <p className="flex items-center gap-2 text-muted-foreground">
            <Spinner /> Loading…
          </p>
        )}
        {props && (
          <div>
            <p className="mb-3 text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Step {index + 1} of {STEPS.length}
            </p>
            <div className="space-y-8">
            {current === "start" && <StartStep {...props} />}
            {current === "android" && <AndroidStep {...props} />}
            {current === "before" && <BackupStep {...props} role="before" />}
            {current === "account" && <AccountStep {...props} />}
            {current === "after" && <BackupStep {...props} role="after" />}
            {current === "done" && <ResultsStep {...props} />}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
