// Light, dark, or the system's setting (the default). The choice is kept in
// this browser only; shadcn's dark theme hangs off a .dark class.

export type Theme = "light" | "dark" | "system"

const KEY = "whatferry-theme"
const systemDark = window.matchMedia("(prefers-color-scheme: dark)")

export function savedTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === "light" || saved === "dark" || saved === "system") return saved
  } catch {
    // storage blocked: use the default
  }
  return "system"
}

export function saveTheme(theme: Theme) {
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // not saved; still applies for this visit
  }
}

export function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && systemDark.matches)
  document.documentElement.classList.toggle("dark", dark)
  document.documentElement.style.colorScheme = dark ? "dark" : "light"
}

/** Re-apply when the system setting changes; returns the unsubscribe. */
export function followSystem(theme: () => Theme) {
  const listener = () => applyTheme(theme())
  systemDark.addEventListener("change", listener)
  return () => systemDark.removeEventListener("change", listener)
}
