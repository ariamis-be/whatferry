// The page's languages. English (locales/en.tsx) is the shape: every other
// language must fill every key, or the build fails. Menu names follow what
// WhatsApp, Android and Apple show in each language.
//
// Not translated here: messages the server writes (errors, the summary to
// send on), which are English everywhere.
//
// To add a language: a file in locales/ typed `Messages`, a row in LANGS,
// and its id in the server's list (src/whatferry/ui/wizard.py, SETTINGS).

import { createContext, useContext } from "react"

import { en, type Messages } from "./locales/en"

export type { Messages }

type Language = {
  /** Kept in settings.json; "zh" predates the other ids, so it stays. */
  id: string
  /** Its own name for itself, as the menu shows it. */
  name: string
  /** The BCP 47 tag for <html lang> and for dates and numbers. */
  tag: string
  /** The browser languages that pick it on a first start. */
  matches: string[]
  rtl?: boolean
  /** English is built in; every other language is its own file, fetched when chosen. */
  load: () => Promise<Messages>
}

// Ordered by the menu: English first, then by each name's English spelling.
const TABLE = [
  { id: "en", name: "English", tag: "en", matches: ["en"], load: async () => en },
  { id: "ar", name: "العربية", tag: "ar", matches: ["ar"], rtl: true, load: () => import("./locales/ar").then((m) => m.ar) },
  { id: "bn", name: "বাংলা", tag: "bn", matches: ["bn"], load: () => import("./locales/bn").then((m) => m.bn) },
  { id: "zh", name: "中文（简体）", tag: "zh-CN", matches: ["zh-cn", "zh-sg", "zh-hans", "zh"], load: () => import("./locales/zh").then((m) => m.zh) },
  { id: "zh-Hant", name: "中文（繁體）", tag: "zh-HK", matches: ["zh-hk", "zh-tw", "zh-mo", "zh-hant"],
    load: () => import("./locales/zh-Hant").then((m) => m.zhHant) },
  { id: "nl", name: "Nederlands", tag: "nl", matches: ["nl"], load: () => import("./locales/nl").then((m) => m.nl) },
  { id: "fr", name: "Français", tag: "fr", matches: ["fr"], load: () => import("./locales/fr").then((m) => m.fr) },
  { id: "de", name: "Deutsch", tag: "de", matches: ["de"], load: () => import("./locales/de").then((m) => m.de) },
  { id: "he", name: "עברית", tag: "he", matches: ["he", "iw"], rtl: true, load: () => import("./locales/he").then((m) => m.he) },
  { id: "hi", name: "हिन्दी", tag: "hi", matches: ["hi"], load: () => import("./locales/hi").then((m) => m.hi) },
  { id: "id", name: "Bahasa Indonesia", tag: "id", matches: ["id", "in"], load: () => import("./locales/id").then((m) => m.id) },
  { id: "it", name: "Italiano", tag: "it", matches: ["it"], load: () => import("./locales/it").then((m) => m.it) },
  { id: "ms", name: "Bahasa Melayu", tag: "ms", matches: ["ms"], load: () => import("./locales/ms").then((m) => m.ms) },
  { id: "fa", name: "فارسی", tag: "fa", matches: ["fa"], rtl: true, load: () => import("./locales/fa").then((m) => m.fa) },
  { id: "pl", name: "Polski", tag: "pl", matches: ["pl"], load: () => import("./locales/pl").then((m) => m.pl) },
  { id: "pt", name: "Português (Brasil)", tag: "pt-BR", matches: ["pt"], load: () => import("./locales/pt").then((m) => m.pt) },
  { id: "ro", name: "Română", tag: "ro", matches: ["ro", "mo"], load: () => import("./locales/ro").then((m) => m.ro) },
  { id: "es", name: "Español", tag: "es", matches: ["es"], load: () => import("./locales/es").then((m) => m.es) },
  { id: "tr", name: "Türkçe", tag: "tr", matches: ["tr"], load: () => import("./locales/tr").then((m) => m.tr) },
  { id: "uk", name: "Українська", tag: "uk", matches: ["uk"], load: () => import("./locales/uk").then((m) => m.uk) },
  { id: "ur", name: "اردو", tag: "ur", matches: ["ur"], rtl: true, load: () => import("./locales/ur").then((m) => m.ur) },
] as const satisfies readonly Language[]

export type Lang = (typeof TABLE)[number]["id"]

// tests/test_ui.py reads the ids from TABLE above, to match the server's list.
export const LANGUAGES: readonly (Language & { id: Lang })[] = TABLE

export function language(lang: Lang): Language {
  return LANGUAGES.find((l) => l.id === lang) ?? LANGUAGES[0]
}

const loaded = new Map<Lang, Promise<Messages>>()

/** A language's words, fetched once; English if its file can't be loaded. */
export function loadMessages(lang: Lang): Promise<Messages> {
  let messages = loaded.get(lang)
  if (!messages) {
    messages = language(lang).load().catch(() => {
      loaded.delete(lang)
      return en
    })
    loaded.set(lang, messages)
  }
  return messages
}

/** The tag for dates and numbers: English keeps the browser's own English (en-GB, en-US…). */
export function locale(lang: Lang): string {
  if (lang !== "en") return language(lang).tag
  return navigator.language.toLowerCase().startsWith("en") ? navigator.language : "en"
}

export const I18nContext = createContext<{ lang: Lang; t: Messages; setLang: (l: Lang) => void }>({
  lang: "en",
  t: en,
  setLang: () => {},
})

export function useI18n() {
  return useContext(I18nContext)
}

/** The language a browser tag picks, if any: the longest match wins, so zh-TW finds Traditional. */
export function fromBrowser(tag: string): Lang | undefined {
  const t = tag.toLowerCase()
  let best: { lang: Lang; length: number } | undefined
  for (const l of LANGUAGES) {
    for (const m of l.matches) {
      if ((t === m || t.startsWith(`${m}-`)) && m.length > (best?.length ?? 0)) best = { lang: l.id, length: m.length }
    }
  }
  return best?.lang
}

/** The language to start in: saved choice, else the browser's first one we have, else English. */
export function toLang(saved: string | undefined, browser: readonly string[] = navigator.languages): Lang {
  const known = LANGUAGES.find((l) => l.id === saved)
  if (known) return known.id
  for (const tag of browser) {
    const lang = fromBrowser(tag)
    if (lang) return lang
  }
  return "en"
}
