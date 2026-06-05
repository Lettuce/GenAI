import { useEffect, useRef } from 'react'
import type { ChatStatus, UIMessage } from 'ai'

import { MessageBubble } from '@/components/chat/MessageBubble'
import { StreamingIndicator } from '@/components/chat/StreamingIndicator'
import { ScrollArea } from '@/components/ui/scroll-area'

type MessageListProps = {
  messages: UIMessage[]
  status: ChatStatus
}

export function MessageList({ messages, status }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, status])

  return (
    <ScrollArea className="flex-1 px-4">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 py-6">
        {messages.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground">
            Ask a question about SEC filings to get started.
          </p>
        ) : null}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        <StreamingIndicator status={status} />
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
