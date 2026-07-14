import type { ChatThread } from '../../lib/api'

interface ThreadSidebarProps {
  threads: ChatThread[]
  activeThreadId: string | null
  loading: boolean
  creating: boolean
  onCreateThread: () => void
  onSelectThread: (threadId: string) => void
}

function formatTitle(thread: ChatThread): string {
  if (thread.title && thread.title.trim()) {
    return thread.title
  }
  return `Thread ${thread.id.slice(0, 8)}`
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  loading,
  creating,
  onCreateThread,
  onSelectThread,
}: ThreadSidebarProps) {
  return (
    <aside className="flex w-full max-w-xs flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-4">
        <button
          type="button"
          onClick={onCreateThread}
          disabled={creating}
          className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {creating ? 'Creating…' : 'New Thread'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {loading ? <p className="px-2 py-3 text-sm text-slate-500">Loading threads…</p> : null}
        {!loading && threads.length === 0 ? <p className="px-2 py-3 text-sm text-slate-500">No conversations yet.</p> : null}

        <ul className="space-y-1">
          {threads.map((thread) => {
            const active = thread.id === activeThreadId
            return (
              <li key={thread.id}>
                <button
                  type="button"
                  onClick={() => onSelectThread(thread.id)}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                    active ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {formatTitle(thread)}
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </aside>
  )
}
