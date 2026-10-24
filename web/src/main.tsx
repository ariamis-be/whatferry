import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { applyTheme, savedTheme } from "./theme"

// Before the first render, so the page never flashes the wrong theme.
applyTheme(savedTheme())

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
