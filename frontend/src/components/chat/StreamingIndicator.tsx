import type { ChatStatus } from 'ai'

type StreamingIndicatorProps = {
  status: ChatStatus
}

export function StreamingIndicator({ status }: StreamingIndicatorProps) {
  if (status !== 'submitted' && status !== 'streaming') {
    return null
  }

  return (
    <div className="flex items-center gap-2 px-1 text-sm text-muted-foreground">
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-muted-foreground/60" />
        <span className="relative inline-flex size-2 rounded-full bg-muted-foreground" />
      </span>
      {status === 'submitted' ? 'Sending…' : 'Thinking…'}
    </div>
  )
}
