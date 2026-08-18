import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import type { UIMessage } from 'ai'
import { useChat } from '@ai-sdk/react'
import { useNavigate, useParams } from 'react-router-dom'

import { MessageComposer } from '../../components/chat/MessageComposer'
import type { DisplayCitation } from '../../components/chat/MessageList'
import type { DisplayMessage } from '../../components/chat/MessageList'
import { MessageList } from '../../components/chat/MessageList'
import { ThreadSidebar } from '../../components/chat/ThreadSidebar'
import { createChatTransport } from '../../lib/chatTransport'
import {
  ApiError,
  createThread,
  deleteThread,
  listThreadMessages,
  listThreads,
  updateThreadTitle,
  type ChatThread,
} from '../../lib/api'

const CitationDetailPanel = lazy(() =>
  import('../../components/chat/CitationDetailPanel').then((module) => ({ default: module.CitationDetailPanel })),
)

function tokenize(text: string): Set<string> {
  const tokens = text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 3)
  return new Set(tokens)
}

function sentenceCandidates(text: string): string[] {
  const normalized = text.replace(/\r\n/g, '\n').trim()
  if (!normalized) {
    return []
  }

  return normalized
    .split(/(?<=[.!?])\s+|\n+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 0)
}

function overlapScore(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) {
    return 0
  }

  let overlap = 0
  for (const token of a) {
    if (b.has(token)) {
      overlap += 1
    }
  }

  return overlap
}

function pickBestCitation(content: string, citations: DisplayCitation[]): DisplayCitation {
  if (citations.length === 1) {
    return citations[0]
  }

  const sentences = sentenceCandidates(content)
  const sentenceTokenSets = sentences.map((sentence) => tokenize(sentence)).filter((set) => set.size > 0)

  let bestCitation = citations[0]
  let bestScore = -1

  for (const citation of citations) {
    const citationText = citation.quote || citation.excerpt || ''
    const citationTokens = tokenize(citationText)
    let citationBest = 0

    for (const sentenceTokens of sentenceTokenSets) {
      citationBest = Math.max(citationBest, overlapScore(sentenceTokens, citationTokens))
    }

    if (citationBest > bestScore) {
      bestScore = citationBest
      bestCitation = citation
      continue
    }

    if (citationBest === bestScore) {
      const currentTextLength = (citation.quote || citation.excerpt || '').length
      const bestTextLength = (bestCitation.quote || bestCitation.excerpt || '').length
      if (currentTextLength > bestTextLength) {
        bestCitation = citation
      }
    }
  }

  return bestCitation
}

export function ChatPage() {
  const navigate = useNavigate()
  const params = useParams<{ threadId?: string }>()

  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loadingThreads, setLoadingThreads] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [creatingThread, setCreatingThread] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [citationsByMessageId, setCitationsByMessageId] = useState<Record<string, DisplayCitation[]>>({})
  const [selectedCitation, setSelectedCitation] = useState<{ messageId: string; citation: DisplayCitation } | null>(null)
  const [pinnedThreadIds, setPinnedThreadIds] = useState<string[]>(() => {
    try {
      const raw = window.localStorage.getItem('chatPinnedThreadIds')
      if (!raw) {
        return []
      }
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : []
    } catch {
      return []
    }
  })

  const activeThreadId = params.threadId ?? null

  const hasActiveThread = useMemo(() => {
    return activeThreadId !== null && threads.some((thread) => thread.id === activeThreadId)
  }, [activeThreadId, threads])

  const chatTransport = useMemo(() => createChatTransport(), [])

  const {
    messages: uiMessages,
    sendMessage,
    stop,
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
    setPinnedThreadIds((current) => current.filter((threadId) => nextThreads.some((thread) => thread.id === threadId)))
    return nextThreads
  }, [])

  useEffect(() => {
    window.localStorage.setItem('chatPinnedThreadIds', JSON.stringify(pinnedThreadIds))
  }, [pinnedThreadIds])

  const loadMessages = useCallback(async (threadId: string) => {
    setLoadingMessages(true)
    setUiMessages([])
    setCitationsByMessageId({})
    try {
      const nextMessages = await listThreadMessages(threadId)
      const nextCitationsByMessageId: Record<string, DisplayCitation[]> = {}
      const nextUiMessages: UIMessage[] = nextMessages.map((message) => ({
        id: message.id,
        role: message.role,
        parts: [{ type: 'text', text: message.content }],
      }))
      for (const message of nextMessages) {
        nextCitationsByMessageId[message.id] = message.citations
      }
      setUiMessages(nextUiMessages)
      setCitationsByMessageId(nextCitationsByMessageId)
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
          citations: citationsByMessageId[message.id] ?? [],
        }
      })
  }, [citationsByMessageId, uiMessages])

  const selectedCitationForDisplay = useMemo(() => {
    if (!selectedCitation) {
      return null
    }

    const message = displayMessages.find((item) => item.id === selectedCitation.messageId)
    const citation = message?.citations.find((item) => item.chunk_id === selectedCitation.citation.chunk_id)
    return message && citation ? { messageId: message.id, citation } : null
  }, [displayMessages, selectedCitation])

  const citationsForSelectedMessage = useMemo(() => {
    if (!selectedCitationForDisplay) {
      return []
    }

    const message = displayMessages.find((item) => item.id === selectedCitationForDisplay.messageId)
    return message?.citations ?? []
  }, [displayMessages, selectedCitationForDisplay])

  const isStreaming = status === 'submitted' || status === 'streaming'
  const isBlankReadyState = !hasActiveThread && uiMessages.length === 0 && status === 'ready' && !loadingMessages && !loadingThreads
  const displayError = isBlankReadyState ? null : (error ?? chatError?.message ?? null)

  const progressStage = useMemo<'Analyzing' | 'Searching' | 'Reading' | 'Verifying' | 'Answering' | null>(() => {
    if (!isStreaming) {
      return null
    }

    if (status === 'submitted') {
      return 'Analyzing'
    }

    const assistantMessages = displayMessages.filter((message) => message.role === 'assistant')
    const latestAssistant = assistantMessages.at(-1)?.content ?? ''

    if (latestAssistant.includes('Answering')) {
      return 'Answering'
    }
    if (latestAssistant.includes('Verifying')) {
      return 'Verifying'
    }
    if (latestAssistant.includes('Reading')) {
      return 'Reading'
    }
    if (latestAssistant.includes('Searching')) {
      return 'Searching'
    }
    return 'Analyzing'
  }, [displayMessages, isStreaming, status])

  const progressPercent = useMemo(() => {
    if (!isStreaming) {
      return 0
    }

    if (progressStage === 'Analyzing') {
      return status === 'submitted' ? 12 : 18
    }
    if (progressStage === 'Searching') {
      return 34
    }
    if (progressStage === 'Reading') {
      return 56
    }
    if (progressStage === 'Verifying') {
      return 78
    }
    if (progressStage === 'Answering') {
      return 92
    }
    return 10
  }, [isStreaming, progressStage, status])

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
      stop()
      setUiMessages([])
      setCitationsByMessageId({})
      setSelectedCitation(null)
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
    const nextText = text.trim()
    if (!nextText) {
      return
    }

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

    async function submitToThread(targetThreadId: string, targetText: string) {
      await sendMessage(
        { text: targetText },
        {
          body: {
            threadId: targetThreadId,
          },
        },
      )
      await loadMessages(targetThreadId)
      await refreshThreads()
    }

    try {
      await submitToThread(threadId, nextText)
    } catch (err) {
      const fallbackMessage = err instanceof Error ? err.message : 'Failed to stream response'
      const message = fallbackMessage.toLowerCase()

      if (err instanceof ApiError && err.status === 401) {
        setError('Authentication error: your session expired. Please sign in again.')
      } else if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
        setError('This thread is not available.')
        navigate('/chat', { replace: true })
      } else if (err instanceof ApiError && err.status === 422) {
        setError('Validation error: the grounding output failed validation. Please retry your prompt.')
      } else if (message.includes('network') || message.includes('failed to fetch') || message.includes('stream')) {
        setError('Network error: unable to reach the chat service. Check your connection and retry.')
      } else if (message.includes('validation') || message.includes('grounding')) {
        setError('Validation error: the model response could not be grounded to citations. Try rephrasing.')
      } else {
        setError(fallbackMessage)
      }
    }
  }

  async function handleSuggestedPrompt(prompt: string) {
    await handleSubmitMessage(prompt)
  }

  async function handleRetryAssistantMessage(assistantMessageId: string) {
    setError(null)

    const assistantIndex = displayMessages.findIndex((message) => message.id === assistantMessageId && message.role === 'assistant')
    if (assistantIndex < 0) {
      setError('The selected response is no longer available to retry.')
      return
    }

    const previousUserMessage = [...displayMessages]
      .slice(0, assistantIndex)
      .reverse()
      .find((message) => message.role === 'user' && message.content.trim())

    if (!previousUserMessage) {
      setError('No previous user prompt is available to retry for this response.')
      return
    }

    await handleSubmitMessage(previousUserMessage.content)
  }

  function handleOpenCitationsForMessage(messageId: string) {
    setError(null)
    const message = displayMessages.find((item) => item.id === messageId && item.role === 'assistant')

    if (!message || message.citations.length === 0) {
      setError('No stored citations were found for this response.')
      return
    }

    const bestCitation = pickBestCitation(message.content, message.citations)
    setSelectedCitation({ messageId: message.id, citation: bestCitation })
  }

  async function handleDeleteThread(threadId: string) {
    setError(null)
    try {
      await deleteThread(threadId)
      setPinnedThreadIds((current) => current.filter((id) => id !== threadId))

      if (activeThreadId === threadId) {
        setUiMessages([])
        setCitationsByMessageId({})
        setSelectedCitation(null)
      }

      const nextThreads = await refreshThreads()
      const stillPresent = nextThreads.some((thread) => thread.id === threadId)
      if (stillPresent) {
        throw new Error('Delete did not complete. Please retry.')
      }

      if (nextThreads.length === 0) {
        setUiMessages([])
        setCitationsByMessageId({})
        setSelectedCitation(null)
        navigate('/chat', { replace: true })
        return
      }

      if (activeThreadId === threadId) {
        navigate(`/chat/${nextThreads[0].id}`, { replace: true })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete chat')
    }
  }

  function handleTogglePinThread(threadId: string) {
    setPinnedThreadIds((current) => {
      if (current.includes(threadId)) {
        return current.filter((id) => id !== threadId)
      }
      return [threadId, ...current]
    })
  }

  async function handleRenameThread(threadId: string, title: string) {
    setError(null)
    try {
      await updateThreadTitle(threadId, title)
      await refreshThreads()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rename thread')
    }
  }

  return (
    <main className="flex h-[calc(100vh-4rem)] overflow-hidden bg-slate-50">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        pinnedThreadIds={pinnedThreadIds}
        loading={loadingThreads}
        creating={creatingThread}
        onCreateThread={() => void handleCreateThread()}
        onSelectThread={(threadId) => {
          stop()
          setUiMessages([])
          setCitationsByMessageId({})
          setSelectedCitation(null)
          navigate(`/chat/${threadId}`)
        }}
        onRenameThread={(threadId, title) => void handleRenameThread(threadId, title)}
        onTogglePinThread={handleTogglePinThread}
        onDeleteThread={(threadId) => void handleDeleteThread(threadId)}
      />

      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="border-b border-slate-200 bg-white px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{hasActiveThread ? 'Chat Thread' : 'New Chat'}</h2>
          <p className="text-xs text-slate-500">AI research assistant for SEC filing analysis and cited source-grounded answers.</p>
        </div>

        {displayError ? (
          <div className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">{displayError}</div>
        ) : null}

        <div className="min-h-0 flex-1">
          {loadingMessages ? (
            <div className="flex h-full items-center justify-center text-sm text-slate-500">Loading messages…</div>
          ) : (
            <MessageList
              key={activeThreadId ?? 'new-chat'}
              messages={displayMessages}
              isStreaming={isStreaming}
              progressStage={progressStage}
              progressPercent={progressPercent}
              selectedCitationId={selectedCitationForDisplay ? `${selectedCitationForDisplay.messageId}:${selectedCitationForDisplay.citation.chunk_id}` : null}
              onCitationSelect={setSelectedCitation}
              onRetryAssistantMessage={(messageId) => void handleRetryAssistantMessage(messageId)}
              onOpenCitationsForMessage={handleOpenCitationsForMessage}
              onSuggestedPrompt={(prompt) => handleSuggestedPrompt(prompt)}
            />
          )}
        </div>

        <MessageComposer disabled={isStreaming} onSubmit={handleSubmitMessage} />
      </section>

      <Suspense
        fallback={
          <aside className="hidden w-[24rem] shrink-0 border-l border-slate-200 bg-white p-4 md:flex md:flex-col">
            <p className="text-sm text-slate-500">Loading source explorer…</p>
          </aside>
        }
      >
        <CitationDetailPanel selection={selectedCitationForDisplay} citationsForMessage={citationsForSelectedMessage} />
      </Suspense>
    </main>
  )
}
