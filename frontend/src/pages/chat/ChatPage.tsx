import { useCallback, useEffect, useMemo, useState } from 'react'
import type { UIMessage } from 'ai'
import { useChat } from '@ai-sdk/react'
import { useNavigate, useParams } from 'react-router-dom'

import { MessageComposer } from '../../components/chat/MessageComposer'
import type { DisplayMessage } from '../../components/chat/MessageList'
import { MessageList } from '../../components/chat/MessageList'
import { ThreadSidebar } from '../../components/chat/ThreadSidebar'
import { createChatTransport } from '../../lib/chatTransport'
import {
  ApiError,
  createThread,
  listThreadMessages,
  listThreads,
  type ChatThread,
} from '../../lib/api'

export function ChatPage() {
  const navigate = useNavigate()
  const params = useParams<{ threadId?: string }>()

  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loadingThreads, setLoadingThreads] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [creatingThread, setCreatingThread] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeThreadId = params.threadId ?? null

  const hasActiveThread = useMemo(() => {
    return activeThreadId !== null && threads.some((thread) => thread.id === activeThreadId)
  }, [activeThreadId, threads])

  const chatTransport = useMemo(() => createChatTransport(), [])

  const {
    messages: uiMessages,
    sendMessage,
    setMessages: setUiMessages,
    status,
    error: chatError,
    clearError,
  } = useChat<UIMessage>({
    transport: chatTransport,
  })

  const refreshThreads = useCallback(async () => {
    const nextThreads = await listThreads()
    setThreads(nextThreads)
    return nextThreads
  }, [])

  const loadMessages = useCallback(async (threadId: string) => {
    setLoadingMessages(true)
    try {
      const nextMessages = await listThreadMessages(threadId)
      const nextUiMessages: UIMessage[] = nextMessages.map((message) => ({
        id: message.id,
        role: message.role,
        parts: [{ type: 'text', text: message.content }],
      }))
      setUiMessages(nextUiMessages)
    } catch (err) {
      if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
        setUiMessages([])
        navigate('/chat', { replace: true })
        setError('This thread is not available.')
        return
      }
      throw err
    } finally {
      setLoadingMessages(false)
    }
  }, [navigate, setUiMessages])

  const displayMessages = useMemo<DisplayMessage[]>(() => {
    return uiMessages
      .filter(
        (message): message is UIMessage & { role: 'user' | 'assistant' } =>
          message.role === 'user' || message.role === 'assistant',
      )
      .map((message) => {
        const content = message.parts
          .filter((part): part is Extract<UIMessage['parts'][number], { type: 'text' }> => part.type === 'text')
          .map((part) => part.text)
          .join('')

        return {
          id: message.id,
          role: message.role,
          content,
        }
      })
  }, [uiMessages])

  const isStreaming = status === 'submitted' || status === 'streaming'
  const displayError = error ?? chatError?.message ?? null

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
    clearError()

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

    try {
      await sendMessage(
        { text },
        {
          body: {
            threadId,
          },
        },
      )
      await loadMessages(threadId)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Your session expired. Please sign in again.')
      } else if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
        setError('This thread is not available.')
        navigate('/chat', { replace: true })
      } else {
        setError(err instanceof Error ? err.message : 'Failed to stream response')
      }
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

        {displayError ? (
          <div className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">{displayError}</div>
        ) : null}

        {loadingMessages ? (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-500">Loading messages…</div>
        ) : (
          <MessageList messages={displayMessages} isStreaming={isStreaming} />
        )}

        <MessageComposer disabled={isStreaming} onSubmit={handleSubmitMessage} />
      </section>
    </main>
  )
}
