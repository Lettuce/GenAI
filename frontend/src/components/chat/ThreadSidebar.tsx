import { useState } from 'react'
import type { FormEvent } from 'react'

import type { ChatThread } from '../../lib/api'

interface ThreadSidebarProps {
  threads: ChatThread[]
  activeThreadId: string | null
  loading: boolean
  creating: boolean
  onCreateThread: () => void
  onSelectThread: (threadId: string) => void
  onRenameThread: (threadId: string, title: string) => void
}

function formatTitle(thread: ChatThread): string {
  if (thread.title && thread.title.trim()) {
    return thread.title
  }
  return 'New Chat'
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  loading,
  creating,
  onCreateThread,
  onSelectThread,
  onRenameThread,
}: ThreadSidebarProps) {
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')

  function beginRename(thread: ChatThread) {
    setEditingThreadId(thread.id)
    setDraftTitle(thread.title?.trim() || '')
  }

  function cancelRename() {
    setEditingThreadId(null)
    setDraftTitle('')
  }

  function submitRename(event: FormEvent<HTMLFormElement>, threadId: string) {
    event.preventDefault()
    onRenameThread(threadId, draftTitle.trim())
    cancelRename()
  }

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

        <ul className="space-y-2">
          {threads.map((thread) => {
            const active = thread.id === activeThreadId
            const isEditing = editingThreadId === thread.id
            return (
              <li
                key={thread.id}
                className={`rounded-lg border px-1 py-1 shadow-sm transition-colors ${
                  active
                    ? 'border-slate-900 bg-slate-900 text-white'
                    : 'border-slate-200 bg-slate-100/80 text-slate-900 hover:border-slate-300 hover:bg-slate-200/70'
                }`}
              >
                {isEditing ? (
                  <form onSubmit={(event) => submitRename(event, thread.id)} className="space-y-2 p-2">
                    <input
                      value={draftTitle}
                      onChange={(event) => setDraftTitle(event.target.value)}
                      placeholder="New Chat"
                      className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900"
                      autoFocus
                    />
                    <div className="flex justify-end gap-2">
                      <button type="button" onClick={cancelRename} className="rounded px-2 py-1 text-xs text-slate-600 hover:bg-slate-200">
                        Cancel
                      </button>
                      <button type="submit" className="rounded bg-slate-900 px-2 py-1 text-xs text-white">
                        Save
                      </button>
                    </div>
                  </form>
                ) : (
                    <div className="flex items-center gap-1 p-1">
                    <button
                      type="button"
                      onClick={() => onSelectThread(thread.id)}
                      className={`flex-1 rounded-md px-2 py-2 text-left text-sm ${
                        active ? 'text-white' : 'text-slate-700'
                      }`}
                    >
                      {formatTitle(thread)}
                    </button>
                      <button
                      type="button"
                      onClick={() => beginRename(thread)}
                      className={`rounded px-2 py-1 text-xs ${active ? 'text-slate-200 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-200'}`}
                    >
                      Rename
                    </button>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </div>
    </aside>
  )
}
