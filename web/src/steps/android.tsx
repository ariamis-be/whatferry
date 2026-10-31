import { Fragment, useCallback, useEffect, useRef, useState } from "react"
import { CircleCheck, Eye, EyeOff, FileUp, Info, RefreshCw, TriangleAlert } from "lucide-react"

import { api, day, runJob, size, when, type AndroidEntry, type Candidate } from "@/api"
import { Busy, Disclosure, ErrorNotice, Instructions, PageHeader, Path, Section, StatGrid } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useI18n } from "@/i18n"
import { AndroidAccounts } from "@/steps/android-accounts"
import { PhoneCopy } from "@/steps/phone"
import { platformOf, type StepProps } from "@/wizard"

const FOLDERS = [
  "Android/media/com.whatsapp/WhatsApp/Databases",
  "Android/media/com.whatsapp/WhatsApp/accounts/<number>/Databases",
  "Android/media/com.whatsapp.w4b/WhatsApp Business/Databases",
  "WhatsApp/Databases",
]

/** Where WhatsApp keeps its backups on the phone, by setup. */
function BackupFolders() {
  const { t } = useI18n()
  return (
    <Disclosure title={t.android.foldersTitle}>
      <Table>
        <TableBody>
          {FOLDERS.map((folder, i) => (
            <TableRow key={folder}>
              <TableCell className="text-sm">{t.android.folders[i]}</TableCell>
              <TableCell className="font-mono text-xs whitespace-nowrap">{folder}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="pt-2 text-xs text-muted-foreground">{t.android.foldersNote}</p>
    </Disclosure>
  )
}

function findCandidates(): Promise<Candidate[] | Error> {
  return api<{ files: Candidate[] }>("GET", "/api/android/candidates").then(
    (r) => r.files,
    (e: Error) => e,
  )
}

export function AndroidStep({ overview, refresh }: StepProps) {
  const { t } = useI18n()
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
    setBusy(t.android.copyingFile(file.name))
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
    setBusy(t.android.decrypting)
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

  const folders = overview.candidate_folders
  return (
    <>
      <PageHeader title={t.android.title} lead={t.android.lead} />

      {overview.state.direction === "to-android" && (
        <Alert>
          <Info />
          <AlertTitle>{t.android.toAndroidTitle}</AlertTitle>
          <AlertDescription>{t.android.toAndroidBody}</AlertDescription>
        </Alert>
      )}

      <AndroidAccounts overview={overview} refresh={refresh} />

      <Section n={1} title={t.android.makeTitle}>
        <Instructions items={t.android.make} />
        <Alert>
          <Info />
          <AlertTitle>{t.android.multiTitle}</AlertTitle>
          <AlertDescription>{t.android.multiBody}</AlertDescription>
        </Alert>
      </Section>

      <Section n={2} title={t.android.bringTitle}>
        <p className="text-sm text-muted-foreground">{t.android.bringLead}</p>
        <Tabs defaultValue="share">
          <TabsList className="h-auto flex-wrap">
            <TabsTrigger value="share">{t.android.tabs.share}</TabsTrigger>
            <TabsTrigger value="cable">{t.android.tabs.cable}</TabsTrigger>
            <TabsTrigger value="adb">{t.android.tabs.adb}</TabsTrigger>
          </TabsList>
          <TabsContent value="share" className="space-y-3 pt-3">
            <Instructions items={t.android.share} />
            <BackupFolders />
          </TabsContent>
          <TabsContent value="cable" className="space-y-3 pt-3">
            <Instructions items={t.android.cable(platformOf(overview))} />
            <BackupFolders />
          </TabsContent>
          <TabsContent value="adb" className="pt-3">
            <PhoneCopy
              platform={platformOf(overview)}
              folder={overview.phone_folder}
              onCopied={(file) => {
                setFiles((f) => [file, ...(f ?? []).filter((x) => x.path !== file.path)])
                setPath(file.path)
              }}
            />
          </TabsContent>
        </Tabs>
      </Section>

      <Section n={3} title={t.android.chooseTitle}>
        {files === null ? (
          <Busy>{t.android.searching}</Busy>
        ) : files.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t.android.noneFound}</p>
        ) : (
          <RadioGroup value={path} onValueChange={setPath} aria-label={t.android.chooseTitle}>
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
            <FileUp data-icon="inline-start" /> {t.android.chooseFile}
          </Button>
          <Button variant="ghost" onClick={look}>
            <RefreshCw data-icon="inline-start" /> {t.common.searchAgain}
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
          {t.android.searchHint(
            folders.map((f, i) => (
              <Fragment key={f}>
                {i > 0 && (i === folders.length - 1 ? t.android.listAnd : t.android.listSep)}
                <Path className="text-xs">{f}</Path>
              </Fragment>
            )),
          )}
        </p>
      </Section>

      <Section n={4} title={t.android.keyTitle}>
        <div className="grid gap-2">
          <Label htmlFor="android-key">{t.android.keyLabel}</Label>
          <div className="flex gap-2">
            <Input
              id="android-key"
              type={show ? "text" : "password"}
              autoComplete="off"
              spellCheck={false}
              placeholder={t.android.keyPlaceholder}
              className="font-mono"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <Button
              variant="outline"
              size="icon"
              onClick={() => setShow((s) => !s)}
              aria-label={show ? t.android.hideKey : t.android.showKey}
            >
              {show ? <EyeOff /> : <Eye />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">{t.android.keyHint}</p>
        </div>
      </Section>

      <div className="space-y-4">
        <ErrorNotice message={error} />
        {busy && <Busy>{busy}</Busy>}
        <Button variant={checked ? "outline" : "default"} disabled={!path || busy !== null} onClick={inspect}>
          {checked ? t.android.checkAgain : t.android.decrypt}
        </Button>
        {checked && <AndroidResult entry={checked} />}
      </div>
    </>
  )
}

function AndroidResult({ entry }: { entry: AndroidEntry }) {
  const { t } = useI18n()
  const r = entry.report
  const modern = r.layout.startsWith("modern")
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CircleCheck className="size-4 text-primary" />
          {entry.source.split(/[\\/]/).pop()}
          <Badge variant="secondary">{t.common.checked}</Badge>
        </CardTitle>
        <CardDescription>
          {t.android.resultLine(r.header?.app_version ?? "?", r.user_version, when(entry.checked_at))}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!modern && (
          <Alert>
            <TriangleAlert />
            <AlertDescription>{t.android.legacy}</AlertDescription>
          </Alert>
        )}
        <p className="text-sm">{t.common.messagesRange(day(r.first_message), day(r.last_message))}</p>
        <StatGrid counts={r.counts} />
        {Object.keys(r.jid_servers).length > 0 && (
          <Disclosure title={t.android.jidTitle}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.android.jidHead[0]}</TableHead>
                  <TableHead className="text-right">{t.android.jidHead[1]}</TableHead>
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
          {t.android.decryptedCopy} <Path>{entry.run}</Path>
        </p>
      </CardContent>
    </Card>
  )
}
