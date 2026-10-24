import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowRight, CircleCheck, Eye, EyeOff, FileUp, Info, RefreshCw, TriangleAlert } from "lucide-react"

import { api, day, runJob, size, when, type AndroidEntry, type Candidate } from "@/api"
import { Busy, Code, Disclosure, ErrorNotice, Instructions, PageHeader, Path, Section, StatGrid } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PhoneCopy } from "@/steps/phone"
import type { StepProps } from "@/wizard"

/** Where WhatsApp keeps its backups on the phone, by setup. */
function BackupFolders() {
  const rows: [string, string][] = [
    ["One account", "Android/media/com.whatsapp/WhatsApp/Databases"],
    ["Several accounts", "Android/media/com.whatsapp/WhatsApp/accounts/<number>/Databases"],
    ["WhatsApp Business", "Android/media/com.whatsapp.w4b/WhatsApp Business/Databases"],
    ["Android 10 or older", "WhatsApp/Databases"],
  ]
  return (
    <Disclosure title="Where WhatsApp keeps backups on the phone">
      <Table>
        <TableBody>
          {rows.map(([setup, folder]) => (
            <TableRow key={setup}>
              <TableCell className="text-sm">{setup}</TableCell>
              <TableCell className="font-mono text-xs whitespace-normal wrap-anywhere">{folder}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="pt-2 text-xs text-muted-foreground">
        With several accounts, each <Code>accounts/&lt;number&gt;</Code> folder is one account: pick the one whose
        msgstore.db.crypt15 is newest, just after you tapped Back up. Files ending .crypt14 and dated or “increment”
        files can't be used.
      </p>
    </Disclosure>
  )
}

function findCandidates(): Promise<Candidate[] | Error> {
  return api<{ files: Candidate[] }>("GET", "/api/android/candidates").then(
    (r) => r.files,
    (e: Error) => e,
  )
}

export function AndroidStep({ overview, refresh, go }: StepProps) {
  const checked = overview.state.android
  const [files, setFiles] = useState<Candidate[] | null>(null)
  const [path, setPath] = useState<string>("")
  const [key, setKey] = useState("")
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const picker = useRef<HTMLInputElement>(null)

  const showFiles = useCallback((found: Candidate[] | Error) => {
    if (found instanceof Error) {
      setFiles([])
      setError(found.message)
    } else {
      setFiles(found)
      setPath((p) => p || found[0]?.path || "")
    }
  }, [])

  useEffect(() => {
    let live = true
    findCandidates().then((found) => live && showFiles(found))
    return () => {
      live = false
    }
  }, [showFiles])

  function look() {
    setFiles(null)
    findCandidates().then(showFiles)
  }

  async function upload(file: File | undefined) {
    if (!file) return
    setBusy(`Copying ${file.name}…`)
    setError(null)
    try {
      const saved = await api<{ path: string; name: string; size: number }>("POST", "/api/android/upload", file)
      setFiles((f) => [{ ...saved, modified: new Date().toISOString() }, ...(f ?? [])])
      setPath(saved.path)
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(null)
  }

  async function inspect() {
    setBusy("Decrypting and checking the backup…")
    setError(null)
    try {
      await runJob("/api/android/inspect", { path, key })
      setKey("")
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(null)
  }

  return (
    <>
      <PageHeader
        title="Android backup"
        lead="WhatsApp's encrypted backup, with a 64-digit key you write down, can be read here without rooting the phone."
      />

      <Section n={1} title="Make the backup on the Android phone">
        <Instructions
          items={[
            "Open WhatsApp → Settings → Chats → Chat backup → End-to-end encrypted backup → Turn on.",
            "Choose “Use 64-digit encryption key instead”, then generate the key. Write it down or take a screenshot: WhatsApp can't show it again.",
            "Back on Chat backup, tap Back up. This saves a file on the phone even if Google Drive backups are off.",
          ]}
        />
        <Alert>
          <Info />
          <AlertTitle>More than one WhatsApp account on the phone?</AlertTitle>
          <AlertDescription>
            Each account has its own backup and its own key. Switch to the account you want to move (tap your profile
            picture → switch account) before the steps above, and repeat them for each account you want.
          </AlertDescription>
        </Alert>
      </Section>

      <Section n={2} title="Bring the file to this computer">
        <p className="text-sm text-muted-foreground">Any of these works; pick whichever is easiest.</p>
        <Tabs defaultValue="share">
          <TabsList className="h-auto flex-wrap">
            <TabsTrigger value="share">Share from the phone</TabsTrigger>
            <TabsTrigger value="cable">USB file transfer</TabsTrigger>
            <TabsTrigger value="adb">Copy with USB debugging</TabsTrigger>
          </TabsList>

          <TabsContent value="share" className="space-y-3 pt-3">
            <Instructions
              items={[
                <>
                  Open the phone's Files app (Files by Google, or My Files on Samsung) and go to{" "}
                  <Code>Android/media/com.whatsapp/WhatsApp</Code>. Some file apps hide the <Code>Android</Code>{" "}
                  folder; Files by Google shows it.
                </>,
                <>
                  Open <Code>Databases</Code>, or with several accounts <Code>accounts</Code> → the account's number →{" "}
                  <Code>Databases</Code>.
                </>,
                <>
                  Long-press <Code>msgstore.db.crypt15</Code> (the one without a date) and tap Share.
                </>,
                "Send it to this computer, with whatever you have: LocalSend (free, phone and computer on the same Wi-Fi, nothing goes online), Quick Share (Windows), Google Drive, or email or a message to yourself.",
                "Save it in Downloads, then click Search again below.",
              ]}
            />
            <BackupFolders />
          </TabsContent>

          <TabsContent value="cable" className="space-y-3 pt-3">
            <Instructions
              items={[
                "Plug the phone into this computer with a USB cable and unlock it.",
                "On the phone, tap the “Charging this device via USB” notification and choose File transfer.",
                overview.platform === "darwin"
                  ? "A Mac can't open Android phones on its own: install OpenMTP (free, openmtp.ganeshrvel.com) and open the phone in it."
                  : overview.platform === "win32"
                    ? "Open File Explorer: the phone appears under This PC."
                    : "Your file manager shows the phone in its sidebar.",
                "Copy msgstore.db.crypt15 from the folder below into Downloads, then click Search again below.",
              ]}
            />
            <BackupFolders />
          </TabsContent>

          <TabsContent value="adb" className="pt-3">
            <PhoneCopy
              platform={overview.platform}
              folder={overview.phone_folder}
              onCopied={(file) => {
                setFiles((f) => [file, ...(f ?? []).filter((x) => x.path !== file.path)])
                setPath(file.path)
              }}
            />
          </TabsContent>
        </Tabs>
      </Section>

      <Section n={3} title="Choose the file">
        {files === null ? (
          <Busy>Searching…</Busy>
        ) : files.length === 0 ? (
          <p className="text-sm text-muted-foreground">No WhatsApp backup found yet.</p>
        ) : (
          <RadioGroup value={path} onValueChange={setPath} aria-label="Backup file">
            {files.map((f) => (
              <Label
                key={f.path}
                htmlFor={f.path}
                className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-muted/50"
              >
                <RadioGroupItem value={f.path} id={f.path} className="mt-0.5" />
                <span className="grid min-w-0 gap-1">
                  <span className="text-sm font-medium">
                    {f.name}{" "}
                    <span className="font-normal text-muted-foreground">
                      · {size(f.size)} · {when(f.modified)}
                    </span>
                  </span>
                  <Path>{f.path}</Path>
                </span>
              </Label>
            ))}
          </RadioGroup>
        )}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => picker.current?.click()}>
            <FileUp data-icon="inline-start" /> Choose a file…
          </Button>
          <Button variant="ghost" onClick={look}>
            <RefreshCw data-icon="inline-start" /> Search again
          </Button>
          <input
            ref={picker}
            type="file"
            accept=".crypt14,.crypt15,.db"
            className="sr-only"
            tabIndex={-1}
            onChange={(e) => upload(e.target.files?.[0])}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Search again looks for WhatsApp backups in{" "}
          {overview.candidate_folders.map((f, i) => (
            <span key={f}>
              {i > 0 && (i === overview.candidate_folders.length - 1 ? " and " : ", ")}
              <Path className="text-xs">{f}</Path>
            </span>
          ))}
          . Elsewhere? Use Choose a file.
        </p>
      </Section>

      <Section n={4} title="Enter the key">
        <div className="grid gap-2">
          <Label htmlFor="android-key">64-digit key</Label>
          <div className="flex gap-2">
            <Input
              id="android-key"
              type={show ? "text" : "password"}
              autoComplete="off"
              spellCheck={false}
              placeholder="64 characters, spaces are fine"
              className="font-mono"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <Button variant="outline" size="icon" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide key" : "Show key"}>
              {show ? <EyeOff /> : <Eye />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Used once to decrypt, then forgotten. Not needed if you picked an already decrypted msgstore.db.
          </p>
        </div>
      </Section>

      <ErrorNotice message={error} />
      {busy && <Busy>{busy}</Busy>}

      <div className="flex flex-wrap gap-2">
        <Button size="lg" variant={checked ? "outline" : "default"} disabled={!path || busy !== null} onClick={inspect}>
          {checked ? "Check again" : "Decrypt and check"}
        </Button>
        {checked && (
          <Button size="lg" onClick={() => go("before")}>
            Continue <ArrowRight data-icon="inline-end" />
          </Button>
        )}
      </div>

      {checked && <AndroidResult entry={checked} />}
    </>
  )
}

function AndroidResult({ entry }: { entry: AndroidEntry }) {
  const r = entry.report
  const modern = r.layout.startsWith("modern")
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CircleCheck className="size-4 text-primary" />
          {entry.source.split(/[\\/]/).pop()}
          <Badge variant="secondary">Checked</Badge>
        </CardTitle>
        <CardDescription>
          WhatsApp {r.header?.app_version ?? "?"} · database version {r.user_version} · checked {when(entry.checked_at)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!modern && (
          <Alert>
            <TriangleAlert />
            <AlertDescription>{r.layout}</AlertDescription>
          </Alert>
        )}
        <p className="text-sm">
          Messages from <strong>{day(r.first_message)}</strong> to <strong>{day(r.last_message)}</strong>.
        </p>
        <StatGrid counts={r.counts} />
        {Object.keys(r.jid_servers).length > 0 && (
          <Disclosure title="Contact identifiers by type">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Server</TableHead>
                    <TableHead className="text-right">Count</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(r.jid_servers).map(([server, n]) => (
                    <TableRow key={server}>
                      <TableCell className="font-mono text-xs">{server}</TableCell>
                      <TableCell className="text-right tabular-nums">{n.toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
          </Disclosure>
        )}
        <p className="text-xs text-muted-foreground">
          Decrypted copy: <Path>{entry.run}</Path>
        </p>
      </CardContent>
    </Card>
  )
}
