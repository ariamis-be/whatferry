import { TriangleAlert } from "lucide-react"

import { Instructions, PageHeader, Section } from "@/components/bits"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useI18n } from "@/i18n"

// Everything here happens on the iPhone, so there is nothing to check yet:
// the next step's backup comparison shows whether the account was added.
export function AccountStep() {
  const { t } = useI18n()
  return (
    <>
      <PageHeader title={t.account.title} lead={t.account.lead} />

      <Section title={t.account.addTitle}>
        <Instructions items={t.account.steps} />
      </Section>

      <Alert>
        <TriangleAlert />
        <AlertDescription>{t.account.keepAndroid}</AlertDescription>
      </Alert>
    </>
  )
}
