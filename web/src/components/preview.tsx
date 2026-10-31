import { useEffect, useMemo, useRef, useState } from "react"
import { Eye, Image as ImageIcon, Search, Users } from "lucide-react"

import { api, day, num, when, type ChatChange, type PreviewChat, type PreviewChats, type PreviewMessage } from "@/api"
import { Busy, ErrorNotice } from "@/components/bits"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"

const SHOWN = 60

/**
 * The merged database read back: every chat the account will have, and a
 * chat's newest messages as the iPhone will show them. Names and message
 * text come from the local server on request and are never saved.
 */
export function ConversionPreview({ madeAt }: { madeAt: string }) {
  const { t } = useI18n()
  const [found, setFound] = useState<PreviewChats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<"android" | "all">("android")
  const [query, setQuery] = useState("")
  const [all, setAll] = useState(false)
  const [open, setOpen] = useState<PreviewChat | null>(null)

  useEffect(() => {
    let live = true
    api<PreviewChats>("GET", "/api/preview/chats")
      .then((f) => live && setFound(f))
      .catch((e: Error) => live && setError(e.message))
    return () => {
      live = false
    }
  }, [madeAt])

  const chats = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (found?.chats ?? []).filter(
      (c) => (filter === "all" || c.change !== "unchanged") && (!q || c.name.toLowerCase().includes(q) || c.jid.includes(q)),
    )
  }, [found, filter, query])

  if (error) return <ErrorNotice message={error} />
  if (!found) return <Busy>{t.preview.loading}</Busy>

  const shown = all ? chats : chats.slice(0, SHOWN)
  return (
    <Card aria-label={t.preview.title}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Eye className="size-4 text-primary" />
          {t.preview.title}
        </CardTitle>
        <CardDescription>
          {t.preview.totals(num(found.totals.new), num(found.totals.joined), num(found.totals.unchanged), num(found.totals.from_android))}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Tabs value={filter} onValueChange={(v) => setFilter(v as "android" | "all")}>
            <TabsList>
              <TabsTrigger value="android">{t.preview.fromAndroid}</TabsTrigger>
              <TabsTrigger value="all">{t.preview.all}</TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="relative min-w-48 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label={t.preview.search}
              placeholder={t.preview.search}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-8"
            />
          </div>
        </div>

        <ul className="max-h-96 divide-y overflow-y-auto rounded-lg border">
          {shown.length === 0 && <li className="p-3 text-sm text-muted-foreground">{t.preview.noChats}</li>}
          {shown.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setOpen(c)}
                aria-pressed={open?.id === c.id}
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-2.5 text-left outline-none hover:bg-muted/50 focus-visible:bg-muted/50",
                  open?.id === c.id && "bg-muted",
                )}
              >
                <span className="grid min-w-0 flex-1 gap-0.5">
                  <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
                    {c.group && <Users className="size-3.5 shrink-0 text-muted-foreground" aria-label={t.preview.group} />}
                    <span className="truncate">{c.name}</span>
                    <ChangeBadge change={c.change} />
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {t.preview.chatLine(num(c.from_android), num(c.messages), day(c.first), day(c.last))}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
        {!all && chats.length > SHOWN && (
          <Button variant="ghost" size="sm" onClick={() => setAll(true)}>
            {t.preview.showAll(num(chats.length))}
          </Button>
        )}

        {open && <ChatView key={open.id} chat={open} />}
      </CardContent>
    </Card>
  )
}

function ChangeBadge({ change }: { change: ChatChange }) {
  const { t } = useI18n()
  if (change === "new") return <Badge>{t.preview.change.new}</Badge>
  if (change === "joined") return <Badge variant="secondary">{t.preview.change.joined}</Badge>
  return <Badge variant="outline">{t.preview.change.unchanged}</Badge>
}

function ChatView({ chat }: { chat: PreviewChat }) {
  const { t } = useI18n()
  const [messages, setMessages] = useState<PreviewMessage[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let live = true
    api<{ messages: PreviewMessage[] }>("GET", `/api/preview/messages?chat=${chat.id}&limit=80`)
      .then((r) => live && setMessages(r.messages))
      .catch((e: Error) => live && setError(e.message))
    return () => {
      live = false
    }
  }, [chat.id])

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" })
  }, [messages])

  return (
    <div className="space-y-2 rounded-lg border">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <span className="text-sm font-medium">{chat.name}</span>
        <ChangeBadge change={chat.change} />
        <span className="text-xs text-muted-foreground">{t.preview.newest(num(chat.messages))}</span>
      </div>
      <div className="max-h-[32rem] space-y-1.5 overflow-y-auto px-3 pb-3">
        <ErrorNotice message={error} />
        {!messages && !error && <Busy>{t.common.loading}</Busy>}
        {messages?.map((m) => <Bubble key={m.id} m={m} group={chat.group} />)}
        <div ref={end} />
      </div>
    </div>
  )
}

function Bubble({ m, group }: { m: PreviewMessage; group: boolean }) {
  const { t } = useI18n()
  if (m.kind === "system") {
    return <p className="py-1 text-center text-xs text-muted-foreground">{m.text || t.preview.kinds.system}</p>
  }
  const label = m.kind !== "text" ? (t.preview.kinds[m.kind] ?? t.preview.kinds.other) : null
  return (
    <div className={cn("flex", m.from_me ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3 py-1.5 text-sm",
          m.from_me ? "bg-primary/15" : "bg-muted",
          m.from_android && "ring-1 ring-primary/40",
        )}
      >
        {group && !m.from_me && m.sender && <p className="text-xs font-medium text-primary">{m.sender}</p>}
        {m.picture && <Picture id={m.id} />}
        {label && !m.picture && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground italic">
            {m.kind === "image" && <ImageIcon className="size-3" />}
            {label}
          </p>
        )}
        {m.text && <p className="break-words whitespace-pre-wrap">{m.text}</p>}
        <p className="mt-0.5 flex items-center justify-end gap-1.5 text-[0.7rem] text-muted-foreground">
          {m.from_android && <span>{t.preview.androidMark}</span>}
          {when(m.at)}
        </p>
      </div>
    </div>
  )
}

function Picture({ id }: { id: number }) {
  const { t } = useI18n()
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let live = true
    api<{ data: string }>("GET", `/api/preview/picture?message=${id}`)
      .then((r) => live && setSrc(r.data))
      .catch(() => live && setFailed(true))
    return () => {
      live = false
    }
  }, [id])
  if (failed) return <p className="text-xs text-muted-foreground italic">{t.preview.kinds.image}</p>
  if (!src) return <div className="my-1 h-32 w-48 animate-pulse rounded bg-muted-foreground/10" />
  return <img src={src} alt={t.preview.kinds.image} className="my-1 max-h-64 rounded" loading="lazy" />
}
