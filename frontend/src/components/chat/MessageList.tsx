import type { ChatMessage } from '../../lib/api'

interface MessageListProps {
  messages: ChatMessage[]
  streamingAssistantText: string
  isStreaming: boolean
}

export function MessageList({ messages, streamingAssistantText, isStreaming }: MessageListProps) {
  const hasMessages = messages.length > 0 || Boolean(streamingAssistantText)

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

      {isStreaming ? (
        <div className="flex justify-start">
          <div className="max-w-3xl rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-sm">
            {streamingAssistantText || 'Streaming response…'}
          </div>
        </div>
      ) : null}
    </div>
  )
}
