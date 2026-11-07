import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { api, type Settings } from "./api"
import { loadMessages, toLang } from "./i18n"
import { applyTheme, toTheme } from "./theme"

// Saved settings first, before the first render, so the page never flashes
// the wrong theme or language. The server is local: this takes milliseconds.
api<Settings>("GET", "/api/settings")
  .catch((): Settings => ({}))
  .then(async (settings) => {
    const theme = toTheme(settings.theme)
    applyTheme(theme)
    // The language's own file too, so the first render is already in it.
    const lang = toLang(settings.lang)
    const messages = await loadMessages(lang)
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <App initialTheme={theme} initialLang={lang} initialMessages={messages} />
      </StrictMode>,
    )
  })
