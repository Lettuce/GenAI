export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface MessageListProps {
  messages: DisplayMessage[]
  isStreaming: boolean
}

export function MessageList({ messages, isStreaming }: MessageListProps) {
  const hasMessages = messages.length > 0

  if (!hasMessages) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-sm text-slate-500">Start a conversation to test streaming from the FastAPI stub.</p>
      </div>
    )
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.map((message) => (
        <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div
            className={`max-w-3xl rounded-xl px-4 py-3 text-sm shadow-sm ${
              message.role === 'user' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-900'
            }`}
          >
            {message.content}
          </div>
        </div>
      ))}
      {isStreaming ? <p className="px-1 text-xs text-amber-700">Streaming response...</p> : null}
    </div>
  )
}
