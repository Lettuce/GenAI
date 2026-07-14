import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { MessageComposer } from '../../components/chat/MessageComposer'
import { MessageList } from '../../components/chat/MessageList'
import { ThreadSidebar } from '../../components/chat/ThreadSidebar'
import {
  ApiError,
  createThread,
  listThreadMessages,
  listThreads,
  streamChat,
  type ChatMessage,
  type StreamMessage,
  type ChatThread,
} from '../../lib/api'

export function ChatPage() {
  const navigate = useNavigate()
  const params = useParams<{ threadId?: string }>()

  const [threads, setThreads] = useState<ChatThread[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loadingThreads, setLoadingThreads] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [creatingThread, setCreatingThread] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingAssistantText, setStreamingAssistantText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const activeThreadId = params.threadId ?? null

  const hasActiveThread = useMemo(() => {
    return activeThreadId !== null && threads.some((thread) => thread.id === activeThreadId)
  }, [activeThreadId, threads])

  const refreshThreads = useCallback(async () => {
    const nextThreads = await listThreads()
    setThreads(nextThreads)
    return nextThreads
  }, [])

  const loadMessages = useCallback(async (threadId: string) => {
    setLoadingMessages(true)
    try {
      const nextMessages = await listThreadMessages(threadId)
      setMessages(nextMessages)
    } catch (err) {
      if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
        setMessages([])
        navigate('/chat', { replace: true })
        setError('This thread is not available.')
        return
      }
      throw err
    } finally {
      setLoadingMessages(false)
    }
  }, [navigate])

  function toStreamMessages(history: ChatMessage[], nextUserText: string): StreamMessage[] {
    const prior = history
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map<StreamMessage>((message) => ({
        role: message.role,
        content: message.content,
      }))

    return [...prior, { role: 'user', content: nextUserText }]
  }

  useEffect(() => {
    let mounted = true

    async function bootstrap() {
      setLoadingThreads(true)
      setError(null)
      try {
        const nextThreads = await refreshThreads()
        if (!mounted) {
          return
        }

        if (!params.threadId && nextThreads.length > 0) {
          navigate(`/chat/${nextThreads[0].id}`, { replace: true })
          return
        }

        if (params.threadId) {
          await loadMessages(params.threadId)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load chat data')
      } finally {
        if (mounted) {
          setLoadingThreads(false)
        }
      }
    }

    void bootstrap()
    return () => {
      mounted = false
    }
  }, [loadMessages, navigate, params.threadId, refreshThreads])

  async function handleCreateThread() {
    setCreatingThread(true)
    setError(null)
    try {
      const thread = await createThread()
      await refreshThreads()
      navigate(`/chat/${thread.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create thread')
    } finally {
      setCreatingThread(false)
    }
  }

  async function handleSubmitMessage(text: string) {
    setError(null)

    let threadId = activeThreadId
    if (!threadId) {
      const thread = await createThread()
      await refreshThreads()
      threadId = thread.id
      navigate(`/chat/${thread.id}`)
    }

    if (!threadId) {
      return
    }

    setIsStreaming(true)
    setStreamingAssistantText('')

    const outboundMessages = toStreamMessages(messages, text)

    // Optimistic user bubble while backend persists and starts streaming.
    setMessages((current) => [
      ...current,
      {
        id: `local-user-${Date.now()}`,
        thread_id: threadId,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      },
    ])

    try {
      await streamChat(
        threadId,
        outboundMessages,
        (delta) => {
          setStreamingAssistantText((current) => current + delta)
        },
      )
      const nextMessages = await listThreadMessages(threadId)
      setMessages(nextMessages)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Your session expired. Please sign in again.')
      } else if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
        setError('This thread is not available.')
        navigate('/chat', { replace: true })
      } else {
        setError(err instanceof Error ? err.message : 'Failed to stream response')
      }
    } finally {
      setIsStreaming(false)
      setStreamingAssistantText('')
    }
  }

  return (
    <main className="flex min-h-[calc(100vh-4rem)] bg-slate-50">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        loading={loadingThreads}
        creating={creatingThread}
        onCreateThread={() => void handleCreateThread()}
        onSelectThread={(threadId) => navigate(`/chat/${threadId}`)}
      />

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-slate-200 bg-white px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{hasActiveThread ? 'Chat Thread' : 'New Chat'}</h2>
          <p className="text-xs text-slate-500">FastAPI stub stream with persisted history</p>
        </div>

        {error ? (
          <div className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">{error}</div>
        ) : null}

        {loadingMessages ? (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-500">Loading messages…</div>
        ) : (
          <MessageList
            messages={messages}
            streamingAssistantText={streamingAssistantText}
            isStreaming={isStreaming}
          />
        )}

        <MessageComposer disabled={isStreaming} onSubmit={handleSubmitMessage} />
      </section>
    </main>
  )
}
