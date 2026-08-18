import { useState } from 'react'

import { QueryProgressBar } from './QueryProgressBar'

export interface DisplayCitation {
  chunk_id: string
  source_document_id: string
  quote: string | null
  page_number: number | null
  excerpt: string | null
  ticker: string | null
  company_name: string | null
  filing_type: string | null
  filing_year: number | null
  filing_date: string | null
  source_url: string | null
  neighboring_chunks: {
    relation: 'previous' | 'next' | string
    excerpt: string
    page_number: number | null
  }[]
}

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: DisplayCitation[]
}

interface MessageListProps {
  messages: DisplayMessage[]
  isStreaming: boolean
  progressStage: 'Analyzing' | 'Searching' | 'Reading' | 'Verifying' | 'Answering' | null
  progressPercent: number
  selectedCitationId: string | null
  onCitationSelect: (params: { messageId: string; citation: DisplayCitation } | null) => void
  onRetryAssistantMessage: (messageId: string) => void
  onOpenCitationsForMessage: (messageId: string) => void
  onSuggestedPrompt?: (prompt: string) => Promise<void>
}

interface SectionBlock {
  title: 'Analyzing' | 'Searching' | 'Reading' | 'Verifying' | 'Answering'
  body: string[]
}

const SECTION_TITLES: SectionBlock['title'][] = ['Analyzing', 'Searching', 'Reading', 'Verifying', 'Answering']

const SUGGESTED_PROMPTS = [
  'Summarize the biggest risks and revenue drivers in Apple’s latest 10-K.',
  'Compare Microsoft and NVIDIA operating margin trends across recent filings.',
  'What did Amazon say about customer concentration and liquidity in its annual report?',
  'How did Alphabet describe changes in advertising revenue and operating costs?',
  'Compare recent free cash flow trends for Apple and Microsoft.',
  'What are NVIDIA’s main data center growth drivers and risks?',
  'Summarize Meta’s latest comments about capital spending and AI infrastructure.',
  'Which companies reported the strongest cloud growth in their recent filings?',
  'What liquidity risks did major technology companies disclose?',
]

function chooseSuggestedPrompts(): string[] {
  const storageKey = 'document-copilot:last-suggested-prompts'
  const previousSelection = window.sessionStorage.getItem(storageKey)
  let selection: string[] = []

  for (let attempt = 0; attempt < 10; attempt += 1) {
    const shuffled = [...SUGGESTED_PROMPTS]
    for (let index = shuffled.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(Math.random() * (index + 1))
      ;[shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]]
    }

    selection = shuffled.slice(0, 3)
    if (selection.join('|') !== previousSelection) {
      break
    }
  }

  window.sessionStorage.setItem(storageKey, selection.join('|'))
  return selection
}

function parseSectionedContent(content: string): SectionBlock[] | null {
  const normalized = content.replace(/\r\n/g, '\n').trim()
  if (!normalized) {
    return null
  }

  const lines = normalized.split('\n')
  const sections: SectionBlock[] = []
  let current: SectionBlock | null = null

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) {
      continue
    }

    if (SECTION_TITLES.includes(line as SectionBlock['title'])) {
      current = { title: line as SectionBlock['title'], body: [] }
      sections.push(current)
      continue
    }

    if (!current) {
      return null
    }

    current.body.push(line)
  }

  if (sections.length === 0) {
    return null
  }

  const hasAllSections = SECTION_TITLES.every((title, index) => sections[index]?.title === title)
  if (!hasAllSections) {
    return null
  }

  return sections
}

function renderAssistantContent(content: string) {
  const sections = parseSectionedContent(content)
  if (!sections) {
    return <p className="whitespace-pre-wrap">{content}</p>
  }

  return (
    <div className="space-y-3">
      {sections.map((section) => (
        <section key={section.title} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <h4 className="mb-1 text-xs font-semibold tracking-wide text-slate-700 uppercase">{section.title}</h4>
          <div className="space-y-1.5 text-sm text-slate-700">
            {section.body.map((line, index) => {
              const numberedLine = /^(\d+)\.\s+(.+)$/.exec(line)
              if ((section.title === 'Reading' || section.title === 'Answering') && numberedLine) {
                return (
                  <div key={`${section.title}-${index}`} className="flex gap-2 rounded-md bg-slate-50 px-2 py-1.5 leading-5">
                    <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-slate-200 px-1 text-[11px] font-semibold text-slate-700">
                      {numberedLine[1]}
                    </span>
                    <p className="min-w-0">{numberedLine[2]}</p>
                  </div>
                )
              }

              return (
                <p key={`${section.title}-${index}`} className="leading-5">
                  {line}
                </p>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

export function MessageList({
  messages,
  isStreaming,
  progressStage,
  progressPercent,
  selectedCitationId,
  onCitationSelect,
  onRetryAssistantMessage,
  onOpenCitationsForMessage,
  onSuggestedPrompt,
}: MessageListProps) {
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [starterPrompts] = useState(chooseSuggestedPrompts)
  const hasMessages = messages.length > 0
  const latestAssistantIndex = (() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].role === 'assistant') {
        return index
      }
    }
    return -1
  })()

  if (!hasMessages) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 py-8">
        <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-2xl font-semibold tracking-tight text-slate-900">How can I help?</h3>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            I can answer questions from the SEC filing corpus, compare companies across recent annual and quarterly reports,
            and surface cited passages that support the answer. I can’t provide legal, investment advice, or answer questions
            outside the documents in this dataset.
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {starterPrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => {
                  if (onSuggestedPrompt) {
                    void onSuggestedPrompt(prompt)
                  }
                }}
                disabled={isStreaming || !onSuggestedPrompt}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-left text-sm text-slate-700 transition hover:border-slate-300 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  async function copyMessageContent(messageId: string, content: string) {
    const text = content.trim()
    if (!text) {
      return
    }

    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const temp = document.createElement('textarea')
      temp.value = text
      temp.setAttribute('readonly', 'true')
      temp.style.position = 'absolute'
      temp.style.left = '-9999px'
      document.body.appendChild(temp)
      temp.select()
      document.execCommand('copy')
      document.body.removeChild(temp)
    }

    setCopiedMessageId(messageId)
    window.setTimeout(() => {
      setCopiedMessageId((current) => (current === messageId ? null : current))
    }, 1500)
  }

  return (
    <div className="pane-scrollbar h-full space-y-4 overflow-y-auto p-4">
      {messages.map((message, index) => (
        <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className="w-full max-w-3xl space-y-2">
            <div
              className={`rounded-xl px-4 py-3 text-sm shadow-sm ${
                message.role === 'user' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-900'
              }`}
            >
              {message.role === 'assistant' ? renderAssistantContent(message.content) : <p className="whitespace-pre-wrap">{message.content}</p>}

              {message.role === 'assistant' ? (
                <section className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold tracking-wide text-slate-700 uppercase">Source Citations</p>
                    <button
                      type="button"
                      onClick={() => onOpenCitationsForMessage(message.id)}
                      disabled={message.citations.length === 0}
                      className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Open In Source Explorer
                    </button>
                  </div>

                  {message.citations.length === 0 ? (
                    <p className="text-xs text-slate-500">No source citations were attached to this response.</p>
                  ) : (
                    <div className="pane-scrollbar max-h-72 space-y-2 overflow-y-auto pr-1">
                      {message.citations.map((citation, citationIndex) => {
                        const citationId = `${message.id}:${citation.chunk_id}`
                        const isSelected = selectedCitationId === citationId
                        const sourceName = citation.company_name || citation.ticker || 'Source'
                        const documentYear = citation.filing_year ? String(citation.filing_year) : 'Year n/a'
                        const filingBits = [citation.filing_type || null]
                          .filter(Boolean)
                          .join(' ')
                        const pageLabel = citation.page_number ? `Page ${citation.page_number}` : 'Page n/a'
                        const excerpt = citation.quote || citation.excerpt || 'No excerpt available.'

                        return (
                          <button
                            key={`${message.id}:citation-row:${citation.chunk_id}`}
                            type="button"
                            onClick={() => onCitationSelect(isSelected ? null : { messageId: message.id, citation })}
                            className={`w-full rounded-md border px-2 py-2 text-left transition-colors ${
                              isSelected
                                ? 'border-slate-900 bg-slate-900 text-white'
                                : 'border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <p className={`text-xs font-semibold ${isSelected ? 'text-white' : 'text-slate-800'}`}>
                                [{citationIndex + 1}] {sourceName} · {documentYear}
                              </p>
                              <p className={`text-[11px] ${isSelected ? 'text-slate-200' : 'text-slate-500'}`}>{pageLabel}</p>
                            </div>
                            <p className={`mt-1 text-[11px] ${isSelected ? 'text-slate-100' : 'text-slate-600'}`}>
                              {filingBits || 'Filing metadata unavailable'}
                            </p>
                            <p className={`mt-1 line-clamp-2 text-xs ${isSelected ? 'text-slate-100' : 'text-slate-700'}`}>
                              {excerpt}
                            </p>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </section>
              ) : null}

              {message.role === 'assistant' ? (
                <div className="mt-3 flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => onOpenCitationsForMessage(message.id)}
                    disabled={message.citations.length === 0}
                    className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    aria-label="Cite sources used in this response"
                    title={message.citations.length > 0 ? 'Cite Sources' : 'No sources available for this response'}
                  >
                    <span>Cite Sources</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => onRetryAssistantMessage(message.id)}
                    disabled={isStreaming}
                    className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    aria-label="Retry this prompt"
                    title="Retry prompt"
                  >
                    <span>Retry Prompt</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => void copyMessageContent(message.id, message.content)}
                    className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    aria-label="Copy assistant response"
                    title={copiedMessageId === message.id ? 'Copied' : 'Copy'}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-3.5 w-3.5"
                      aria-hidden="true"
                    >
                      <rect x="9" y="9" width="11" height="11" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                    <span>{copiedMessageId === message.id ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
              ) : null}
            </div>

            {isStreaming && latestAssistantIndex === index ? (
              <QueryProgressBar visible stage={progressStage} progress={progressPercent} compact />
            ) : null}
          </div>
        </div>
      ))}
      {isStreaming ? <p className="px-1 text-xs text-amber-700">Streaming response...</p> : null}
    </div>
  )
}
