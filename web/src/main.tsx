import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { api, type Settings } from "./api"
import { toLang } from "./i18n"
import { applyTheme, toTheme } from "./theme"

// Saved settings first, before the first render, so the page never flashes
// the wrong theme or language. The server is local: this takes milliseconds.
api<Settings>("GET", "/api/settings")
  .catch((): Settings => ({}))
  .then((settings) => {
    const theme = toTheme(settings.theme)
    applyTheme(theme)
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <App initialTheme={theme} initialLang={toLang(settings.lang)} />
      </StrictMode>,
    )
  })
