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

import { ar } from "./locales/ar"
import { bn } from "./locales/bn"
import { de } from "./locales/de"
import { en, type Messages } from "./locales/en"
import { es } from "./locales/es"
import { fa } from "./locales/fa"
import { fr } from "./locales/fr"
import { he } from "./locales/he"
import { hi } from "./locales/hi"
import { id } from "./locales/id"
import { it } from "./locales/it"
import { ms } from "./locales/ms"
import { nl } from "./locales/nl"
import { pl } from "./locales/pl"
import { pt } from "./locales/pt"
import { ro } from "./locales/ro"
import { tr } from "./locales/tr"
import { uk } from "./locales/uk"
import { ur } from "./locales/ur"
import { zh } from "./locales/zh"
import { zhHant } from "./locales/zh-Hant"

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
  messages: Messages
}

// Ordered by the menu: English first, then by each name's English spelling.
const TABLE = [
  { id: "en", name: "English", tag: "en", matches: ["en"], messages: en },
  { id: "ar", name: "العربية", tag: "ar", matches: ["ar"], rtl: true, messages: ar },
  { id: "bn", name: "বাংলা", tag: "bn", matches: ["bn"], messages: bn },
  { id: "zh", name: "中文（简体）", tag: "zh-CN", matches: ["zh-cn", "zh-sg", "zh-hans", "zh"], messages: zh },
  { id: "zh-Hant", name: "中文（繁體）", tag: "zh-HK", matches: ["zh-hk", "zh-tw", "zh-mo", "zh-hant"],
    messages: zhHant },
  { id: "nl", name: "Nederlands", tag: "nl", matches: ["nl"], messages: nl },
  { id: "fr", name: "Français", tag: "fr", matches: ["fr"], messages: fr },
  { id: "de", name: "Deutsch", tag: "de", matches: ["de"], messages: de },
  { id: "he", name: "עברית", tag: "he", matches: ["he", "iw"], rtl: true, messages: he },
  { id: "hi", name: "हिन्दी", tag: "hi", matches: ["hi"], messages: hi },
  { id: "id", name: "Bahasa Indonesia", tag: "id", matches: ["id", "in"], messages: id },
  { id: "it", name: "Italiano", tag: "it", matches: ["it"], messages: it },
  { id: "ms", name: "Bahasa Melayu", tag: "ms", matches: ["ms"], messages: ms },
  { id: "fa", name: "فارسی", tag: "fa", matches: ["fa"], rtl: true, messages: fa },
  { id: "pl", name: "Polski", tag: "pl", matches: ["pl"], messages: pl },
  { id: "pt", name: "Português (Brasil)", tag: "pt-BR", matches: ["pt"], messages: pt },
  { id: "ro", name: "Română", tag: "ro", matches: ["ro", "mo"], messages: ro },
  { id: "es", name: "Español", tag: "es", matches: ["es"], messages: es },
  { id: "tr", name: "Türkçe", tag: "tr", matches: ["tr"], messages: tr },
  { id: "uk", name: "Українська", tag: "uk", matches: ["uk"], messages: uk },
  { id: "ur", name: "اردو", tag: "ur", matches: ["ur"], rtl: true, messages: ur },
] as const satisfies readonly Language[]

export type Lang = (typeof TABLE)[number]["id"]

// tests/test_ui.py reads the ids from TABLE above, to match the server's list.
export const LANGUAGES: readonly (Language & { id: Lang })[] = TABLE

export function language(lang: Lang): Language {
  return LANGUAGES.find((l) => l.id === lang) ?? LANGUAGES[0]
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
