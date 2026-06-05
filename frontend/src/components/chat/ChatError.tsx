type ChatErrorProps = {
  error: Error
}

export function ChatError({ error }: ChatErrorProps) {
  return (
    <div
      className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
      role="alert"
    >
      {error.message || 'Something went wrong while sending your message.'}
    </div>
  )
}
