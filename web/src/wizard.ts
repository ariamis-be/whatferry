import type { Overview } from "@/api"

export const STEPS = [
  { id: "start", title: "Start" },
  { id: "android", title: "Android backup" },
  { id: "before", title: "iPhone backup" },
  { id: "account", title: "Add account" },
  { id: "after", title: "Second backup" },
  { id: "done", title: "Results" },
] as const

export type StepId = (typeof STEPS)[number]["id"]

export const CHECKLIST = [
  ["add-account", "On the iPhone, open WhatsApp → Settings and choose Add account (next to your name at the top)."],
  ["register-number", "Register the Android phone's number and enter the code WhatsApp sends. WhatsApp on the Android phone signs out: that's expected, and your backup file is already safe on this computer."],
  ["leave-empty", "If WhatsApp offers to restore chats for the new account, skip it. The new account should start empty."],
  ["new-backup", "Make a new encrypted backup of the iPhone, the same way as before."],
] as const

/** What every step gets: the server's view, a way to reload it, and navigation. */
export interface StepProps {
  overview: Overview
  refresh: () => Promise<void>
  go: (step: StepId) => void
}

export function nextStep(step: StepId): StepId {
  const i = STEPS.findIndex((s) => s.id === step)
  return STEPS[Math.min(i + 1, STEPS.length - 1)].id
}
