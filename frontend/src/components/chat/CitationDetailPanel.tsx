import type { DisplayCitation } from './MessageList'

interface CitationSelection {
  messageId: string
  citation: DisplayCitation
}

interface CitationDetailPanelProps {
  selection: CitationSelection | null
  citationsForMessage: DisplayCitation[]
}

interface ExtractedSignals {
  products: string[]
  years: string[]
  amounts: string[]
  productNumbers: string[]
  percentages: string[]
  entities: string[]
}

interface SourceTableRow {
  citation: DisplayCitation
  count: number
}

const PRODUCT_KEYWORDS = [
  'aws',
  'prime',
  'azure',
  'office 365',
  'copilot',
  'ads',
  'advertising',
  'services',
  'cloud',
  'devices',
  'subscriptions',
  'marketplace',
  'logistics',
  'fulfillment',
  'windows',
  'xbox',
  'youtube',
  'search',
]

function escapeMarkdownCell(value: string) {
  return value.replace(/\|/g, '\\|').replace(/\n/g, ' ').trim()
}

function formatSourceText(value: string | null | undefined) {
  if (!value) {
    return 'No excerpt available.'
  }

  const normalized = value
    .replace(/\r\n/g, '\n')
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\$\s+/g, '$')
    .replace(/\s*,\s*=\s*\.?/g, ', ')
    .replace(/\s*=\s*(?=[,.])/g, '')
    .trim()

  const listItems = normalized.split(/\s*,\s*/).map((item) => item.replace(/^=\s*/, '').trim()).filter(Boolean)
  const deduplicatedItems: string[] = []
  const seenItems = new Set<string>()
  for (const item of listItems) {
    const cleanedItem = item.replace(/[.]+$/g, '').trim()
    const key = cleanedItem.toLowerCase().replace(/[^a-z0-9%]+/g, ' ').trim()
    if (!key || seenItems.has(key)) {
      continue
    }
    seenItems.add(key)
    deduplicatedItems.push(cleanedItem)
  }

  return deduplicatedItems.join(', ').replace(/,\s*([.!?])/g, '$1').trim()
}

function uniqueLimit(values: string[], limit = 8) {
  const seen = new Set<string>()
  const uniqueValues: string[] = []
  for (const value of values) {
    const cleaned = formatSourceText(value)
    const key = cleaned.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
    if (!key || seen.has(key)) {
      continue
    }
    seen.add(key)
    uniqueValues.push(cleaned)
  }
  return uniqueValues.slice(0, limit)
}

function extractMatches(text: string, pattern: RegExp, limit = 8) {
  return uniqueLimit([...text.matchAll(pattern)].map((match) => match[0]), limit)
}

function extractProducts(text: string) {
  const lower = text.toLowerCase()
  return uniqueLimit(PRODUCT_KEYWORDS.filter((keyword) => lower.includes(keyword)).map((keyword) => keyword.toUpperCase()), 8)
}

function extractEntities(text: string) {
  const matches = text.match(/\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|[A-Z]{2,})\b/g) ?? []
  return uniqueLimit(matches, 8)
}

function extractSignals(text: string): ExtractedSignals {
  return {
    products: extractProducts(text),
    years: extractMatches(text, /\b(?:19|20)\d{2}\b/g, 6),
    amounts: extractMatches(text, /\$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|trillion|m|b|t))?/gi, 8),
    productNumbers: extractMatches(text, /\b(?:SKU\s*[:#-]?\s*[A-Z0-9-]+|[A-Z]{1,5}-\d{2,}|[A-Z0-9]{3,}-[A-Z0-9-]{2,})\b/g, 8),
    percentages: extractMatches(text, /\b\d+(?:\.\d+)?%\b/g, 8),
    entities: extractEntities(text),
  }
}

function formatSignalCell(values: string[]) {
  if (values.length === 0) {
    return 'n/a'
  }
  return values.join(', ')
}

function quickSignalSummary(text: string) {
  const signals = extractSignals(text)
  const parts = [
    signals.products[0],
    signals.years[0],
    signals.amounts[0],
    signals.productNumbers[0],
  ].filter(Boolean)

  return parts.length > 0 ? parts.join(' | ') : 'n/a'
}

function buildSourceRows(citations: DisplayCitation[]): SourceTableRow[] {
  const rows = new Map<string, SourceTableRow>()
  for (const citation of citations) {
    const key = [citation.source_document_id, citation.filing_type || '', citation.filing_year || '', citation.page_number || ''].join('|')
    const existing = rows.get(key)
    if (existing) {
      existing.count += 1
    } else {
      rows.set(key, { citation, count: 1 })
    }
  }
  return [...rows.values()]
}

function buildMarkdownTable(rows: SourceTableRow[]) {
  const header = '| Source | Filing | Year | Page | Quote |'
  const divider = '| --- | --- | --- | --- | --- |'
  const markdownRows = rows.map(({ citation, count }) => {
    const source = escapeMarkdownCell(citation.company_name || citation.ticker || 'Source')
    const filing = escapeMarkdownCell(citation.filing_type || 'n/a')
    const year = citation.filing_year ? String(citation.filing_year) : 'n/a'
    const page = citation.page_number ? String(citation.page_number) : 'n/a'
    const quote = escapeMarkdownCell(formatSourceText(citation.quote || citation.excerpt || 'No excerpt available'))
    return `| ${source} (${count}) | ${filing} | ${year} | ${page} | ${quote} |`
  })

  return [header, divider, ...markdownRows].join('\n')
}

export function CitationDetailPanel({ selection, citationsForMessage }: CitationDetailPanelProps) {
  if (!selection) {
    return (
      <aside className="pane-scrollbar hidden min-h-0 w-[24rem] shrink-0 border-l border-slate-200 bg-white p-4 md:flex md:flex-col md:overflow-y-auto">
        <h3 className="text-sm font-semibold text-slate-900">Source Explorer</h3>
        <p className="mt-2 text-sm text-slate-500">Click a citation chip to inspect source metadata and neighboring chunks.</p>
      </aside>
    )
  }

  const citation = selection.citation
  const sourceRows = buildSourceRows(citationsForMessage)
  const markdownTable = buildMarkdownTable(sourceRows)
  const previousChunk = citation.neighboring_chunks.find((chunk) => chunk.relation === 'previous')
  const nextChunk = citation.neighboring_chunks.find((chunk) => chunk.relation === 'next')
  const selectedChunkText = formatSourceText(citation.quote || citation.excerpt)
  const previousChunkText = formatSourceText(previousChunk?.excerpt)
  const nextChunkText = formatSourceText(nextChunk?.excerpt)
  const selectedSignals = extractSignals(selectedChunkText)
  const previousSignals = extractSignals(previousChunkText)
  const nextSignals = extractSignals(nextChunkText)

  return (
    <aside className="hidden min-h-0 w-[24rem] shrink-0 border-l border-slate-200 bg-white p-4 md:flex md:flex-col md:overflow-hidden">
      <div className="pane-scrollbar min-h-0 overflow-y-auto pr-1">
        <h3 className="text-sm font-semibold text-slate-900">Source Explorer</h3>
        <p className="mt-1 text-xs text-slate-500">Best-match citation is auto-highlighted, with neighboring chunks for surrounding context.</p>

        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-slate-100 text-slate-700">
              <tr>
                <th className="border-b border-slate-200 px-2 py-2 font-semibold">Source</th>
                <th className="border-b border-slate-200 px-2 py-2 font-semibold">Filing</th>
                <th className="border-b border-slate-200 px-2 py-2 font-semibold">Year</th>
                <th className="border-b border-slate-200 px-2 py-2 font-semibold">Page</th>
                <th className="border-b border-slate-200 px-2 py-2 font-semibold">Key Values</th>
              </tr>
            </thead>
            <tbody>
              {sourceRows.map(({ citation: item, count }) => {
                const isSelected = item.chunk_id === citation.chunk_id
                return (
                  <tr key={`${item.source_document_id}:${item.page_number ?? 'na'}`} className={isSelected ? 'bg-slate-50' : 'bg-white'}>
                    <td className="border-b border-slate-100 px-2 py-2 text-slate-800 break-words">
                      <span>{item.company_name || item.ticker || 'Source'}</span>
                      {count > 1 ? <span className="ml-1 text-[10px] text-slate-500">({count} chunks)</span> : null}
                    </td>
                    <td className="border-b border-slate-100 px-2 py-2 text-slate-700 break-words">{item.filing_type || 'n/a'}</td>
                    <td className="border-b border-slate-100 px-2 py-2 text-slate-700">{item.filing_year ?? 'n/a'}</td>
                    <td className="border-b border-slate-100 px-2 py-2 text-slate-700">{item.page_number ?? 'n/a'}</td>
                    <td className="border-b border-slate-100 px-2 py-2 text-slate-700 break-words">{quickSignalSummary(formatSourceText(item.quote || item.excerpt))}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <details className="mt-3 rounded border border-slate-200 bg-slate-50 p-2">
          <summary className="cursor-pointer text-xs font-medium text-slate-700">Markdown table representation</summary>
          <pre className="pane-scrollbar mt-2 max-h-36 overflow-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-slate-700">{markdownTable}</pre>
        </details>

        <div className="mt-4 space-y-3 text-xs text-slate-700">
          <section className="rounded border border-slate-200 bg-white p-2">
            <p className="mb-1 font-semibold text-slate-800">Selected chunk</p>
            <div className="mb-2 overflow-x-auto rounded border border-slate-200">
              <table className="w-full border-collapse text-left text-[11px]">
                <tbody>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Products</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(selectedSignals.products)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Years</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(selectedSignals.years)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Amounts</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(selectedSignals.amounts)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Product #</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(selectedSignals.productNumbers)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Percentages</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(selectedSignals.percentages)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Other Terms</th>
                    <td className="px-2 py-1 text-slate-700">{formatSignalCell(selectedSignals.entities)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="pane-scrollbar max-h-48 overflow-y-auto rounded border border-slate-100 bg-slate-50 p-2">
              <p className="whitespace-pre-wrap break-words leading-5">{selectedChunkText}</p>
            </div>
            {citation.source_url ? (
              <a href={citation.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-slate-700 underline">
                Open source filing
              </a>
            ) : null}
          </section>

          <section className="rounded border border-slate-200 bg-white p-2">
            <p className="mb-1 font-semibold text-slate-800">Previous chunk</p>
            <div className="mb-2 overflow-x-auto rounded border border-slate-200">
              <table className="w-full border-collapse text-left text-[11px]">
                <tbody>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Products</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(previousSignals.products)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Years</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(previousSignals.years)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Amounts</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(previousSignals.amounts)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Product #</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(previousSignals.productNumbers)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Percentages</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(previousSignals.percentages)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Other Terms</th>
                    <td className="px-2 py-1 text-slate-700">{formatSignalCell(previousSignals.entities)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="pane-scrollbar max-h-40 overflow-y-auto rounded border border-slate-100 bg-slate-50 p-2">
              <p className="whitespace-pre-wrap break-words leading-5">{previousChunkText}</p>
            </div>
            {previousChunk ? <p className="mt-1 text-[11px] text-slate-500">Page {previousChunk.page_number ?? 'n/a'}</p> : null}
          </section>

          <section className="rounded border border-slate-200 bg-white p-2">
            <p className="mb-1 font-semibold text-slate-800">Next chunk</p>
            <div className="mb-2 overflow-x-auto rounded border border-slate-200">
              <table className="w-full border-collapse text-left text-[11px]">
                <tbody>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Products</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(nextSignals.products)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Years</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(nextSignals.years)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Amounts</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(nextSignals.amounts)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Product #</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(nextSignals.productNumbers)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 border-b border-slate-100 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Percentages</th>
                    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">{formatSignalCell(nextSignals.percentages)}</td>
                  </tr>
                  <tr>
                    <th className="w-32 bg-slate-50 px-2 py-1 font-semibold text-slate-700">Other Terms</th>
                    <td className="px-2 py-1 text-slate-700">{formatSignalCell(nextSignals.entities)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="pane-scrollbar max-h-40 overflow-y-auto rounded border border-slate-100 bg-slate-50 p-2">
              <p className="whitespace-pre-wrap break-words leading-5">{nextChunkText}</p>
            </div>
            {nextChunk ? <p className="mt-1 text-[11px] text-slate-500">Page {nextChunk.page_number ?? 'n/a'}</p> : null}
          </section>
        </div>
      </div>
    </aside>
  )
}
