import { useState, type FormEvent, type KeyboardEvent } from 'react'
import type { ChatStatus } from 'ai'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

type ChatInputProps = {
  status: ChatStatus
  onSend: (text: string) => void
}

export function ChatInput({ status, onSend }: ChatInputProps) {
  const [input, setInput] = useState('')
  const isBusy = status === 'submitted' || status === 'streaming'

  function submit() {
    const text = input.trim()
    if (!text || isBusy) {
      return
    }

    onSend(text)
    setInput('')
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t bg-background px-4 py-4"
    >
      <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
        <Textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about SEC filings…"
          rows={2}
          disabled={isBusy}
          className="min-h-[3rem] resize-none"
        />
        <Button type="submit" disabled={isBusy || input.trim() === ''}>
          Send
        </Button>
      </div>
    </form>
  )
}
