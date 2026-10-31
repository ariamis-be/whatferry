import type { Direction, Overview } from "@/api"

// Titles and texts live in i18n.tsx; these are the ids the server knows.
export const STEPS = ["start", "android", "before", "account", "after", "convert", "write", "restore", "done"] as const

export type StepId = (typeof STEPS)[number]

export type { Direction }

/**
 * The steps each direction goes through. iPhone -> Android checks the iPhone
 * backup first (the chats come from it), then the Android one, and needs no
 * second account or second backup.
 */
export function stepsFor(direction: Direction | undefined): readonly StepId[] {
  return direction === "to-android" ? ["start", "before", "android", "convert", "write", "restore", "done"] : STEPS
}

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
