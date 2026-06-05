import type { UIMessage } from 'ai'

import { cn } from '@/lib/utils'

type MessageBubbleProps = {
  message: UIMessage
}

function textFromParts(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('')
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const text = textFromParts(message)
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'border bg-card text-card-foreground',
        )}
      >
        <p className="whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}
