// Light, dark, or the system's setting (the default). The choice is kept by
// the whatferry server (see saveSettings); shadcn's dark theme hangs off a
// .dark class.

export type Theme = "light" | "dark" | "system"

const systemDark = window.matchMedia("(prefers-color-scheme: dark)")

export function toTheme(saved: string | undefined): Theme {
  if (saved === "light" || saved === "dark" || saved === "system") return saved
  return "system"
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
