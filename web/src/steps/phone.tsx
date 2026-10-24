import { useCallback, useEffect, useState } from "react"
import { CircleCheck, Download, Smartphone, TriangleAlert, Usb } from "lucide-react"

import { api, runJob, size, when, type Candidate, type PhoneBackup, type PhoneStatus } from "@/api"
import { Busy, Code, Disclosure, ErrorNotice, Instructions, Path } from "@/components/bits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const INSTALL_ADB: Record<string, string[]> = {
  darwin: ["With Homebrew: brew install --cask android-platform-tools", "Or download platform-tools from Google (link below) and unzip it."],
  win32: ["In a terminal: winget install Google.PlatformTools", "Or download platform-tools from Google (link below) and unzip it."],
  other: ["Debian or Ubuntu: sudo apt install adb · Fedora: sudo dnf install android-tools", "Or download platform-tools from Google (link below) and unzip it."],
}

function fetchStatus(): Promise<PhoneStatus | Error> {
  return api<PhoneStatus>("GET", "/api/android/phone").catch((e: Error) => e)
}

/** Copy a backup straight off a phone plugged in with USB debugging. */
export function PhoneCopy({ platform, folder, onCopied }: {
  platform: string
  folder: string
  onCopied: (file: Candidate) => void
}) {
  const [status, setStatus] = useState<PhoneStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copying, setCopying] = useState<string | null>(null)
  const [copied, setCopied] = useState<Candidate | null>(null)

  const show = useCallback((s: PhoneStatus | Error) => {
    if (s instanceof Error) setError(s.message)
    else setStatus(s)
  }, [])

  useEffect(() => {
    let live = true
    fetchStatus().then((s) => live && show(s))
    return () => {
      live = false
    }
  }, [show])

  function look() {
    setStatus(null)
    setError(null)
    fetchStatus().then(show)
  }

  async function copy(serial: string, path: string) {
    setCopying(path)
    setError(null)
    try {
      const file = await runJob<Candidate>("/api/android/phone/pull", { serial, path })
      setCopied(file)
      onCopied(file)
    } catch (e) {
      setError((e as Error).message)
    }
    setCopying(null)
  }

  const phones = status?.devices ?? []
  const ready = phones.filter((p) => p.ready)

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Plug the phone into this computer and whatferry copies the backup itself, straight into{" "}
        <Code>{folder}</Code>. Needs USB debugging on the phone and adb on this computer; you can turn debugging off
        again afterwards.
      </p>

      {status === null && !error && <Busy>Looking for adb and connected phones…</Busy>}
      <ErrorNotice message={error ?? status?.error} />

      {status && !status.adb && (
        <Alert>
          <TriangleAlert />
          <AlertTitle>adb isn't installed on this computer</AlertTitle>
          <AlertDescription className="space-y-2">
            <span className="block">adb is Google's free tool for talking to Android phones over USB.</span>
            <Instructions items={INSTALL_ADB[platform] ?? INSTALL_ADB.other} />
            <span className="block">
              Google's download: <Code>developer.android.com/tools/releases/platform-tools</Code>. If adb is somewhere
              whatferry doesn't look, start it with <Code>WHATFERRY_ADB=/path/to/adb</Code>.
            </span>
          </AlertDescription>
        </Alert>
      )}

      {status?.adb && ready.length === 0 && (
        <div className="space-y-3 rounded-lg border p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium">
            <Usb className="size-4" /> Turn on USB debugging
          </h3>
          <Instructions
            items={[
              "On the phone, open Settings → About phone and tap Build number seven times. Enter your PIN if asked; it says “You are now a developer”. (Samsung: Settings → About phone → Software information → Build number.)",
              "Go back to Settings → System → Developer options and turn on USB debugging.",
              "Plug the phone into this computer with a USB cable and unlock it.",
              "Tap Allow on “Allow USB debugging?”. Ticking “Always allow from this computer” saves doing it again.",
              "Click Find phone below.",
            ]}
          />
          <p className="text-xs text-muted-foreground">
            When you're done: Developer options → turn USB debugging off.
          </p>
        </div>
      )}

      {phones
        .filter((p) => !p.ready)
        .map((p) => (
          <Alert key={p.serial}>
            <Smartphone />
            <AlertTitle>{p.model ?? "Android phone"} isn't ready</AlertTitle>
            <AlertDescription>{p.advice}</AlertDescription>
          </Alert>
        ))}

      {ready.map((phone) => (
        <div key={phone.serial} className="space-y-3 rounded-lg border p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium">
            <Smartphone className="size-4" /> {phone.model ?? "Android phone"}
            <Badge variant="secondary">Connected</Badge>
          </h3>
          <ErrorNotice message={phone.error} />
          {(() => {
            const backups = phone.backups ?? []
            const usable = backups.filter((b) => b.usable)
            const other = backups.filter((b) => !b.usable)
            const row = (b: PhoneBackup) => (
              <li key={b.path} className="flex flex-wrap items-start justify-between gap-3 rounded-md bg-muted/50 p-3">
                <span className="grid min-w-0 gap-1">
                  <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {b.name}
                    <Badge variant="outline">
                      {b.app}
                      {b.account ? ` · account ${b.account}` : ""}
                    </Badge>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {size(b.size)} · {when(b.modified)}
                  </span>
                  <Path>{b.path}</Path>
                  {b.note && <span className="text-xs text-muted-foreground">{b.note}</span>}
                </span>
                {b.usable && (
                  <Button size="sm" disabled={copying !== null} onClick={() => copy(phone.serial, b.path)}>
                    <Download data-icon="inline-start" />
                    {copying === b.path ? "Copying…" : "Copy"}
                  </Button>
                )}
              </li>
            )
            return (
              <>
                {backups.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No WhatsApp backup on this phone yet. Make one first (step 1), then click Find phone again.
                  </p>
                )}
                {backups.length > 0 && usable.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No usable backup yet: turn on the 64-digit encrypted backup and tap Back up (step 1), then click
                    Find phone again.
                  </p>
                )}
                {usable.length > 0 && <ul className="space-y-2">{usable.map(row)}</ul>}
                {other.length > 0 && (
                  <Disclosure title={`${other.length} other ${other.length === 1 ? "file" : "files"} that can't be used`}>
                    <ul className="space-y-2">{other.map(row)}</ul>
                  </Disclosure>
                )}
              </>
            )
          })()}
        </div>
      ))}

      {copied && (
        <Alert>
          <CircleCheck />
          <AlertTitle>Copied {copied.name}</AlertTitle>
          <AlertDescription>
            It's chosen below, in step 3. <Path>{copied.path}</Path>
          </AlertDescription>
        </Alert>
      )}

      {(status || error) && (
        <Button variant="outline" onClick={look}>
          <Usb data-icon="inline-start" /> Find phone
        </Button>
      )}
    </div>
  )
}
