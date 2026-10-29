import { useCallback, useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight, Check, Languages, Monitor, Moon, ShieldCheck, Sun } from "lucide-react"

import { api, saveSettings, setLocale, TOKEN, type Overview, type State } from "@/api"
import { ErrorNotice } from "@/components/bits"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Spinner } from "@/components/ui/spinner"
import { I18nContext, LANGS, locale, MESSAGES, type Lang } from "@/i18n"
import { cn } from "@/lib/utils"
import { AccountStep } from "@/steps/account"
import { AndroidStep } from "@/steps/android"
import { BackupStep } from "@/steps/backup"
import { ConvertStep } from "@/steps/convert"
import { RestoreStep } from "@/steps/restore"
import { ResultsStep } from "@/steps/results"
import { StartStep } from "@/steps/start"
import { WriteStep } from "@/steps/write"
import { applyTheme, followSystem, type Theme } from "@/theme"
import { STEPS, type StepId } from "@/wizard"

function isDone(id: StepId, s: State) {
  switch (id) {
    case "start": return Boolean(s.android || s.before)
    case "android": return Boolean(s.android)
    case "before": return Boolean(s.before)
    // Nothing to check on the phone itself; the second backup proves it,
    // unless the chats go to an account that already exists.
    case "account": return s.destination === "existing" || Boolean(s.after)
    case "after": return Boolean(s.after)
    case "convert": return Boolean(s.converted)
    case "write": return Boolean(s.written)
    case "restore": return Boolean(s.restored)
    default: return false
  }
}

/** A step the chosen destination makes unnecessary. */
function isSkipped(id: StepId, s: State) {
  return id === "after" && s.destination === "existing"
}

/** For a step that works on an earlier one's result, the step still to do first. */
function blockedBy(id: StepId, s: State): StepId | null {
  if (id === "write" && !s.converted) return "convert"
  if (id === "restore" && !s.written) return s.converted ? "write" : "convert"
  if (id === "done" && !s.restored) return s.written ? "restore" : s.converted ? "write" : "convert"
  return null
}

export default function App({ initialTheme, initialLang }: { initialTheme: Theme; initialLang: Lang }) {
  const [lang, setLangState] = useState<Lang>(initialLang)
  const [theme, setThemeState] = useState<Theme>(initialTheme)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [current, setCurrent] = useState<StepId>("start")

  const t = MESSAGES[lang]
  setLocale(locale(lang))
  const i18n = useMemo(() => ({
    lang,
    t,
    setLang: (l: Lang) => {
      saveSettings({ lang: l })
      setLangState(l)
    },
  }), [lang, t])

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en"
  }, [lang])

  useEffect(() => {
    applyTheme(theme)
    return followSystem(() => theme)
  }, [theme])

  const refresh = useCallback(async () => {
    setOverview(await api<Overview>("GET", "/api/overview"))
  }, [])

  useEffect(() => {
    if (!TOKEN) return
    api<Overview>("GET", "/api/overview")
      .then((o) => {
        setOverview(o)
        // A saved step that's locked now (a backup checked again since) opens on what it waits for.
        const saved = STEPS.find((s) => s === o.state.step)
        if (saved) setCurrent(blockedBy(saved, o.state) ?? saved)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  const go = useCallback((step: StepId) => {
    setCurrent(step)
    window.scrollTo(0, 0)
    document.getElementById("main")?.focus()
    api("POST", "/api/step", { step }).catch(() => {})
  }, [])

  const state = overview?.state ?? {}
  const index = STEPS.indexOf(current)
  const props = overview ? { overview, refresh, go } : null
  const back = STEPS.slice(0, index).filter((s) => !isSkipped(s, state)).at(-1) ?? null
  const next = STEPS.slice(index + 1).find((s) => !isSkipped(s, state)) ?? null
  const nextBlocker = next ? blockedBy(next, state) : null

  return (
    <I18nContext.Provider value={i18n}>
      <div className="flex min-h-svh flex-col">
        <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
          <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:max-w-4xl xl:max-w-5xl">
            <div className="flex h-14 items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 font-semibold">
                <img src="/static/icon.svg" alt="" className="size-6" />
                whatferry
              </div>
              <div className="flex items-center gap-1">
                <p className="mr-2 hidden items-center gap-1.5 text-xs text-muted-foreground md:flex">
                  <ShieldCheck className="size-3.5" />
                  {t.header.tagline}
                </p>
                <DropdownMenu modal={false}>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" aria-label={t.header.language}>
                      <Languages data-icon="inline-start" />
                      {LANGS.find((l) => l.id === lang)?.name}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-auto min-w-44 [&_[role=menuitemradio]]:whitespace-nowrap">
                    <DropdownMenuLabel>{t.header.language}</DropdownMenuLabel>
                    <DropdownMenuRadioGroup value={lang} onValueChange={(v) => i18n.setLang(v as Lang)}>
                      {LANGS.map((l) => (
                        <DropdownMenuRadioItem key={l.id} value={l.id} lang={l.id === "zh" ? "zh-CN" : "en"}>
                          {l.name}
                        </DropdownMenuRadioItem>
                      ))}
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
                <DropdownMenu modal={false}>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon-sm" aria-label={t.header.theme}>
                      {theme === "light" ? <Sun /> : theme === "dark" ? <Moon /> : <Monitor />}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-auto min-w-44 [&_[role=menuitemradio]]:whitespace-nowrap">
                    <DropdownMenuLabel>{t.header.theme}</DropdownMenuLabel>
                    <DropdownMenuRadioGroup
                      value={theme}
                      onValueChange={(v) => {
                        saveSettings({ theme: v })
                        setThemeState(v as Theme)
                      }}
                    >
                      <DropdownMenuRadioItem value="system">
                        <Monitor /> {t.header.system}
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="light">
                        <Sun /> {t.header.light}
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="dark">
                        <Moon /> {t.header.dark}
                      </DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
            <nav aria-label={t.stepOf(index + 1, STEPS.length)} className="pb-3">
              <ol className="flex gap-1.5">
                {STEPS.map((step, i) => {
                  const done = isDone(step, state)
                  const skipped = isSkipped(step, state)
                  const active = step === current
                  const blocker = active ? null : blockedBy(step, state)
                  const label = t.stepLabel(i + 1, t.steps[step], done)
                  return (
                    <li key={step} className={cn("min-w-0 flex-1", active && "max-sm:flex-[3]")}>
                      <button
                        type="button"
                        onClick={() => go(step)}
                        disabled={blocker !== null}
                        title={blocker ? t.nav.first(t.steps[blocker]) : undefined}
                        aria-current={active ? "step" : undefined}
                        aria-label={
                          skipped ? `${label} (${t.stepSkipped})` : blocker ? `${label} (${t.nav.first(t.steps[blocker])})` : label
                        }
                        className="group flex w-full flex-col gap-2 rounded-sm py-1 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <span
                          className={cn(
                            "h-1 rounded-full bg-border transition-colors",
                            (done || active) && "bg-primary",
                            active && !done && "bg-primary/60",
                            skipped && !active && "bg-transparent bg-[repeating-linear-gradient(90deg,var(--border)_0_4px,transparent_4px_8px)]",
                          )}
                        />
                        <span
                          aria-hidden
                          className={cn(
                            "flex items-center gap-1 truncate text-xs text-muted-foreground group-hover:text-foreground",
                            active && "font-medium text-foreground",
                            skipped && !active && "line-through decoration-muted-foreground/60",
                          )}
                        >
                          {done ? <Check className="size-3 shrink-0" /> : <span className="tabular-nums">{i + 1}</span>}
                          <span className={cn("truncate", !active && "max-sm:hidden")}>{t.steps[step]}</span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ol>
            </nav>
          </div>
        </header>

        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-3xl px-4 pt-10 pb-6 outline-none sm:px-6 sm:pt-14 lg:max-w-4xl xl:max-w-5xl">
          {!TOKEN && <ErrorNotice message={t.common.openWithLink} />}
          {error && <ErrorNotice message={t.common.cantReach(error)} />}
          {TOKEN && !error && !props && (
            <p className="flex items-center gap-2 text-muted-foreground">
              <Spinner /> {t.common.loading}
            </p>
          )}
          {props && (
            <>
              <p className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {t.stepOf(index + 1, STEPS.length)}
                {/* With several Android accounts, every step says which one it's for. */}
                {props.overview.android_accounts.length > 1 && current !== "start" && (
                  <span className="rounded-full bg-muted px-2 py-0.5 tracking-normal normal-case">
                    {t.android.movingAccount(
                      props.overview.android_accounts.find((a) => a.current)?.number_ends ?? null,
                    )}
                  </span>
                )}
              </p>
              {/* Text runs the same width as the tables and boxes around it, so it never stops short of them. */}
              <div className="space-y-8 pb-10">
                {current === "start" && <StartStep {...props} />}
                {current === "android" && <AndroidStep {...props} />}
                {current === "before" && <BackupStep {...props} role="before" />}
                {current === "account" && <AccountStep overview={props.overview} go={go} />}
                {current === "after" && <BackupStep {...props} role="after" />}
                {current === "convert" && <ConvertStep {...props} />}
                {current === "write" && <WriteStep {...props} />}
                {current === "restore" && <RestoreStep {...props} />}
                {current === "done" && <ResultsStep {...props} />}
              </div>

              {/* Right after the step, and stuck to the window bottom while a long step scrolls: back on the left, on on the right. */}
              <footer className="sticky bottom-0 z-10 -mx-4 flex items-center justify-between gap-3 border-t bg-background/85 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/70 sm:-mx-6 sm:px-6">
                {back ? (
                  <Button variant="ghost" onClick={() => go(back)}>
                    <ArrowLeft data-icon="inline-start" /> {t.nav.back}
                  </Button>
                ) : (
                  <span />
                )}
                {next && (
                  <div className="flex items-center gap-3">
                    {nextBlocker && <span className="text-sm text-muted-foreground">{t.nav.first(t.steps[nextBlocker])}</span>}
                    <Button
                      size="lg"
                      variant={current === "start" || (current === "account" && state.destination) || isDone(current, state) || isSkipped(current, state) ? "default" : "outline"}
                      disabled={nextBlocker !== null}
                      onClick={() => go(next)}
                    >
                      {current === "start" ? t.nav.start : t.nav.continue} <ArrowRight data-icon="inline-end" />
                    </Button>
                  </div>
                )}
              </footer>
            </>
          )}
        </main>
      </div>
    </I18nContext.Provider>
  )
}
