import { useState } from 'react'
import type { FormEvent } from 'react'

interface MessageComposerProps {
  disabled: boolean
  onSubmit: (text: string) => Promise<void>
}

export function MessageComposer({ disabled, onSubmit }: MessageComposerProps) {
  const [text, setText] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = text.trim()
    if (!next || disabled) {
      return
    }

    await onSubmit(next)
    setText('')
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-200 p-4">
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Ask about the filing corpus..."
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-500"
          disabled={disabled}
        />
        <button
          type="submit"
          disabled={disabled || text.trim().length === 0}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          Send
        </button>
      </div>
    </form>
  )
}
