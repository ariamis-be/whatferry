import type { ReactNode } from "react"
import { ChevronRight, CircleAlert } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Spinner } from "@/components/ui/spinner"
import { num, type Counts } from "@/api"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"

export { Code, Path } from "@/components/code"

export function StatGrid({ counts, className }: { counts: Counts; className?: string }) {
  const { t } = useI18n()
  const items = Object.entries(counts).filter(([, n]) => n !== null && n !== undefined)
  return (
    <dl className={cn("grid grid-cols-2 gap-2 sm:grid-cols-4", className)}>
      {items.map(([label, n]) => (
        <div key={label} className="rounded-lg bg-muted/60 px-3 py-2.5">
          <dd className="text-xl font-semibold tabular-nums">{num(n)}</dd>
          <dt className="text-xs text-muted-foreground">{t.counts[label] ?? label}</dt>
        </div>
      ))}
    </dl>
  )
}

/** A numbered part of a step: "1. Make the backup". */
export function Section({ n, title, children }: { n?: number; title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2.5 text-base font-semibold">
        {n !== undefined && (
          <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular-nums">
            {n}
          </span>
        )}
        {title}
      </h2>
      {children}
    </section>
  )
}

export function Instructions({ items }: { items: ReactNode[] }) {
  return (
    <ol className="list-decimal space-y-1.5 ps-5 text-sm leading-relaxed marker:font-medium marker:text-muted-foreground">
      {items.map((item, i) => (
        <li key={i} className="ps-1">
          {item}
        </li>
      ))}
    </ol>
  )
}

export function ErrorNotice({ message }: { message: string | null | undefined }) {
  const { t } = useI18n()
  if (!message) return null
  return (
    <Alert variant="destructive" role="alert">
      <CircleAlert />
      <AlertTitle>{t.common.failed}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}

export function Busy({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner />
      {children}
    </p>
  )
}

/** A titled section that opens on click, for detail most people skip. */
export function Disclosure({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Collapsible className="group/disclosure">
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="-ms-2.5 text-muted-foreground">
          <ChevronRight
            data-icon="inline-start"
            className="transition-transform rtl:-scale-x-100 group-data-[state=open]/disclosure:rotate-90 rtl:group-data-[state=open]/disclosure:-rotate-90"
          />
          {title}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2">{children}</CollapsibleContent>
    </Collapsible>
  )
}

export function PageHeader({ title, lead }: { title: string; lead: string }) {
  return (
    <header className="space-y-2">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      <p className="text-muted-foreground">{lead}</p>
    </header>
  )
}
