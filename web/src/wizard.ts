import type { Overview } from "@/api"

// Titles and texts live in i18n.tsx; these are the ids the server knows.
export const STEPS = ["start", "android", "before", "account", "after", "done"] as const

export type StepId = (typeof STEPS)[number]

export const CHECKLIST = ["add-account", "register-number", "leave-empty", "new-backup"] as const

/** What every step gets: the server's view and a way to reload it. */
export interface StepProps {
  overview: Overview
  refresh: () => Promise<void>
  go: (step: StepId) => void
}

export type Platform = "darwin" | "win32" | "other"

export function platformOf(overview: Overview): Platform {
  return overview.platform === "darwin" || overview.platform === "win32" ? overview.platform : "other"
}
