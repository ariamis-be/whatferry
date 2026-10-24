import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

// wrap-anywhere breaks a long path only where it would overflow; break-all
// would split short names like msgstore.db.crypt15 mid-word.
export function Path({ children, className }: { children: ReactNode; className?: string }) {
  return <code className={cn("font-mono text-xs wrap-anywhere text-muted-foreground", className)}>{children}</code>
}

export function Code({ children }: { children: ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] wrap-anywhere">{children}</code>
}
