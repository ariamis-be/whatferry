import { TriangleAlert } from "lucide-react"

import { Instructions, PageHeader, Section } from "@/components/bits"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useI18n } from "@/i18n"
import type { StepProps } from "@/wizard"

// Everything here happens on the iPhone, so there is nothing to check yet:
// the next step's backup comparison shows whether the account appeared.
// What to do depends on where the chats go, chosen after the first backup.
export function AccountStep({ overview, go }: Pick<StepProps, "overview" | "go">) {
  const { t } = useI18n()
  const destination = overview.state.destination

  if (!destination) {
    return (
      <>
        <PageHeader title={t.account.title} lead={t.account.none} />
        <Button variant="outline" onClick={() => go("before")}>
          {t.account.goChoose}
        </Button>
      </>
    )
  }

  if (destination === "existing") {
    return <PageHeader title={t.account.existing.title} lead={t.account.existing.lead} />
  }

  const setup = destination === "setup"
  return (
    <>
      <PageHeader
        title={setup ? t.account.setup.title : t.account.title}
        lead={setup ? t.account.setup.lead : t.account.lead}
      />

      <Section title={setup ? t.account.setup.sectionTitle : t.account.addTitle}>
        <Instructions items={setup ? t.account.setup.steps : t.account.steps} />
      </Section>

      <Alert>
        <TriangleAlert />
        <AlertDescription>{t.account.keepAndroid}</AlertDescription>
      </Alert>
    </>
  )
}
