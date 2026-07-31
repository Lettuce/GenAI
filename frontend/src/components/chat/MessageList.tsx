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
}

interface SectionBlock {
  title: 'Analyzing' | 'Searching' | 'Reading' | 'Verifying' | 'Answering'
  body: string[]
}

const SECTION_TITLES: SectionBlock['title'][] = ['Analyzing', 'Searching', 'Reading', 'Verifying', 'Answering']

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
          <div className="space-y-1 text-sm text-slate-700">
            {section.body.map((line, index) => (
              <p key={`${section.title}-${index}`} className="leading-5">
                {line}
              </p>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export function MessageList({ messages, isStreaming, progressStage, progressPercent }: MessageListProps) {
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [expandedCitationId, setExpandedCitationId] = useState<string | null>(null)
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
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-sm text-slate-500">Start a conversation to test streaming from the FastAPI stub.</p>
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
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.map((message, index) => (
        <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className="w-full max-w-3xl space-y-2">
            <div
              className={`rounded-xl px-4 py-3 text-sm shadow-sm ${
                message.role === 'user' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-900'
              }`}
            >
              {message.role === 'assistant' ? renderAssistantContent(message.content) : <p className="whitespace-pre-wrap">{message.content}</p>}

              {message.role === 'assistant' && message.citations.length > 0 ? (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-semibold text-slate-600">Citations</p>
                  <div className="flex flex-wrap gap-2">
                    {message.citations.map((citation) => {
                      const citationId = `${message.id}:${citation.chunk_id}`
                      const isExpanded = expandedCitationId === citationId
                      const titleParts = [
                        citation.company_name || citation.ticker || 'Source',
                        citation.filing_type || null,
                        citation.filing_year ? String(citation.filing_year) : null,
                      ].filter(Boolean)
                      const chipLabel = titleParts.join(' - ') || 'Source'
                      const pageLabel = citation.page_number ? `p.${citation.page_number}` : 'page n/a'

                      return (
                        <div key={citationId} className="w-full">
                          <button
                            type="button"
                            onClick={() => setExpandedCitationId(isExpanded ? null : citationId)}
                            className="inline-flex max-w-full items-center rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 hover:bg-slate-50"
                          >
                            <span className="truncate">{chipLabel}</span>
                            <span className="ml-2 text-slate-500">{pageLabel}</span>
                          </button>

                          {isExpanded ? (
                            <div className="mt-2 rounded-md border border-slate-200 bg-white p-3 text-xs text-slate-700">
                              <p className="whitespace-pre-wrap leading-5">{citation.quote || citation.excerpt || 'No excerpt available.'}</p>
                              {citation.source_url ? (
                                <a
                                  href={citation.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="mt-2 inline-block text-slate-600 underline"
                                >
                                  Open source filing
                                </a>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : null}

              {message.role === 'assistant' ? (
                <div className="mt-3 flex justify-end">
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
