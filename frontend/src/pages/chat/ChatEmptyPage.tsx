export function ChatEmptyPage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <h1 className="text-lg font-medium text-foreground">Start a conversation</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        Choose an existing thread from the sidebar or create a new chat to ask questions about
        SEC filings.
      </p>
    </div>
  )
}
