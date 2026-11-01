import { cn } from "cn"
import { Loader2Icon } from "lucide-react"

function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    // Always shown beside text that says what is loading: the text is what gets read out.
    <Loader2Icon data-slot="spinner" aria-hidden="true" className={cn("size-4 animate-spin", className)} {...props} />
  )
}

export { Spinner }
