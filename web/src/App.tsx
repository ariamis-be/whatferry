import { useCallback, useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight, Check, Languages, Monitor, Moon, ShieldCheck, Sun } from "lucide-react"

import { api, setLocale, TOKEN, type Overview, type State } from "@/api"
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
import { I18nContext, initialLang, LANGS, locale, MESSAGES, saveLang, type Lang } from "@/i18n"
import { cn } from "@/lib/utils"
import { AccountStep } from "@/steps/account"
import { AndroidStep } from "@/steps/android"
import { BackupStep } from "@/steps/backup"
import { ResultsStep } from "@/steps/results"
import { StartStep } from "@/steps/start"
import { applyTheme, followSystem, savedTheme, saveTheme, type Theme } from "@/theme"
import { CHECKLIST, STEPS, type StepId } from "@/wizard"

function isDone(id: StepId, s: State) {
  switch (id) {
    case "start": return Boolean(s.android || s.before)
    case "android": return Boolean(s.android)
    case "before": return Boolean(s.before)
    case "account": return CHECKLIST.every((key) => s.checklist?.[key])
    case "after": return Boolean(s.after)
    default: return false
  }
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(initialLang)
  const [theme, setThemeState] = useState<Theme>(savedTheme)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [current, setCurrent] = useState<StepId>("start")

  const t = MESSAGES[lang]
  setLocale(locale(lang))
  const i18n = useMemo(() => ({
    lang,
    t,
    setLang: (l: Lang) => {
      saveLang(l)
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
        const saved = STEPS.find((s) => s === o.state.step)
        if (saved) setCurrent(saved)
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
  const back = index > 0 ? STEPS[index - 1] : null
  const next = index < STEPS.length - 1 ? STEPS[index + 1] : null

  return (
    <I18nContext.Provider value={i18n}>
      <div className="flex min-h-svh flex-col">
        <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
          <div className="mx-auto max-w-3xl px-4 sm:px-6">
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
                        saveTheme(v as Theme)
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
                  const active = step === current
                  return (
                    <li key={step} className={cn("min-w-0 flex-1", active && "max-sm:flex-[3]")}>
                      <button
                        type="button"
                        onClick={() => go(step)}
                        aria-current={active ? "step" : undefined}
                        aria-label={t.stepLabel(i + 1, t.steps[step], done)}
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

        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-3xl px-4 pt-10 pb-6 outline-none sm:px-6 sm:pt-14">
          {!TOKEN && <ErrorNotice message={t.common.openWithLink} />}
          {error && <ErrorNotice message={t.common.cantReach(error)} />}
          {TOKEN && !error && !props && (
            <p className="flex items-center gap-2 text-muted-foreground">
              <Spinner /> {t.common.loading}
            </p>
          )}
          {props && (
            <>
              <p className="mb-3 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {t.stepOf(index + 1, STEPS.length)}
              </p>
              <div className="space-y-8 pb-10">
                {current === "start" && <StartStep {...props} />}
                {current === "android" && <AndroidStep {...props} />}
                {current === "before" && <BackupStep {...props} role="before" />}
                {current === "account" && <AccountStep {...props} />}
                {current === "after" && <BackupStep {...props} role="after" />}
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
                  <Button
                    size="lg"
                    variant={current === "start" || isDone(current, state) ? "default" : "outline"}
                    onClick={() => go(next)}
                  >
                    {current === "start" ? t.nav.start : t.nav.continue} <ArrowRight data-icon="inline-end" />
                  </Button>
                )}
              </footer>
            </>
          )}
        </main>
      </div>
    </I18nContext.Provider>
  )
}
