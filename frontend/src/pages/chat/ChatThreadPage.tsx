import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useChat } from '@ai-sdk/react'
import type { UIMessage } from 'ai'

import { ChatError } from '@/components/chat/ChatError'
import { ChatInput } from '@/components/chat/ChatInput'
import { MessageList } from '@/components/chat/MessageList'
import { useChatTransport } from '@/hooks/useChatTransport'
import { useThreads } from '@/hooks/useThreads'
import { getThreadMessages } from '@/lib/chat'
import { ApiError } from '@/lib/http'

type ChatThreadViewProps = {
  threadId: string
  initialMessages: UIMessage[]
}

function ChatThreadView({ threadId, initialMessages }: ChatThreadViewProps) {
  const { refreshThreads } = useThreads()
  const transport = useChatTransport(threadId)

  const { messages, sendMessage, status, error } = useChat({
    id: threadId,
    messages: initialMessages,
    transport,
    onFinish: () => {
      void refreshThreads()
    },
  })

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <MessageList messages={messages} status={status} />

      <div className="mx-auto w-full max-w-3xl px-4 pb-2">
        {error ? <ChatError error={error} /> : null}
      </div>

      <ChatInput
        status={status}
        onSend={(text) => {
          void sendMessage({ text })
        }}
      />
    </div>
  )
}

function ChatThreadLoader({ threadId }: { threadId: string }) {
  const navigate = useNavigate()
  const [initialMessages, setInitialMessages] = useState<UIMessage[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    async function load() {
      try {
        const messages = await getThreadMessages(threadId)
        if (mounted) {
          setInitialMessages(messages)
        }
      } catch (err) {
        if (!mounted) {
          return
        }

        if (err instanceof ApiError && err.status === 404) {
          navigate('/chats', { replace: true })
          return
        }

        if (err instanceof ApiError) {
          setLoadError(err.message)
        } else {
          setLoadError('Could not load this conversation.')
        }
      }
    }

    void load()

    return () => {
      mounted = false
    }
  }, [threadId, navigate])

  if (loadError) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="text-sm text-destructive" role="alert">
          {loadError}
        </p>
      </div>
    )
  }

  if (initialMessages === null) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="text-sm text-muted-foreground">Loading conversation…</p>
      </div>
    )
  }

  return <ChatThreadView threadId={threadId} initialMessages={initialMessages} />
}

export function ChatThreadPage() {
  const { threadId } = useParams()

  if (!threadId) {
    return null
  }

  return <ChatThreadLoader key={threadId} threadId={threadId} />
}
