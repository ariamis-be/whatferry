import { ArrowRight, Cable, Clock, Lock, Smartphone } from "lucide-react"

import { Code, Instructions, PageHeader, Section } from "@/components/bits"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { StepProps } from "@/wizard"

const NEEDS = [
  { icon: Smartphone, text: "The Android phone, with WhatsApp and the chats you want to move." },
  { icon: Smartphone, text: "The iPhone, with WhatsApp already set up for its own number." },
  { icon: Cable, text: "A cable to connect the iPhone to this computer." },
  { icon: Clock, text: "About an hour, mostly waiting for backups. You can close this and come back: progress is saved." },
]

export function StartStep({ overview, go }: StepProps) {
  return (
    <>
      <PageHeader
        title="Move WhatsApp chats from Android to iPhone"
        lead="This wizard checks both phones' backups so the transfer can be built for your exact setup. It only reads: nothing is written to either phone or to any backup."
      />

      <Section title="You'll need">
        <ul className="grid gap-2 sm:grid-cols-2">
          {NEEDS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex gap-3 rounded-lg border p-3 text-sm">
              <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              {text}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="What happens">
        <Instructions
          items={[
            "Make an encrypted WhatsApp backup on the Android phone and bring the file here.",
            "Back up the iPhone, so the wizard can see how WhatsApp stores your current account.",
            "Add the Android number to WhatsApp on the iPhone as a second account.",
            "Back up the iPhone again. Comparing the two backups shows exactly where the new account's chats will go.",
          ]}
        />
      </Section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="size-4" /> What stays private
          </CardTitle>
          <CardDescription>Nothing leaves this computer.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1.5 pl-5 text-sm">
            <li>The page only talks to whatferry on this computer. Nothing is uploaded anywhere.</li>
            <li>Keys and passphrases are used once and never saved.</li>
            <li>
              Decrypted copies are kept in <Code>{overview.home}</Code>, readable only by you. Delete it when you're
              done.
            </li>
          </ul>
        </CardContent>
      </Card>

      <Button size="lg" onClick={() => go("android")}>
        Start <ArrowRight data-icon="inline-end" />
      </Button>
    </>
  )
}
