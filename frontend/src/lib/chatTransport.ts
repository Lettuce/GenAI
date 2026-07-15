import type { UIMessage } from 'ai'
import { DefaultChatTransport } from 'ai'

import { env } from './env'
import { supabase } from './supabase'

interface BackendMessage {
  role: 'user' | 'assistant'
  content: string
}

function extractTextFromUiMessage(message: UIMessage): string {
  const textParts = message.parts
    .filter((part): part is Extract<UIMessage['parts'][number], { type: 'text' }> => part.type === 'text')
    .map((part) => part.text)
    .filter((text) => text.trim().length > 0)

  return textParts.join('\n').trim()
}

function mapUiMessagesToBackendMessages(messages: UIMessage[]): BackendMessage[] {
  return messages
    .filter(
      (message): message is UIMessage & { role: 'user' | 'assistant' } =>
        message.role === 'user' || message.role === 'assistant',
    )
    .map((message) => ({
      role: message.role,
      content: extractTextFromUiMessage(message),
    }))
    .filter((message) => message.content.length > 0)
}

export function createChatTransport() {
  return new DefaultChatTransport({
    api: `${env.apiBaseUrl.replace(/\/$/, '')}/chat/stream`,
    prepareSendMessagesRequest: async (options) => {
      const threadId = options.body && 'threadId' in options.body ? String(options.body.threadId ?? '') : ''
      if (!threadId) {
        throw new Error('threadId is required for chat streaming')
      }

      const { data } = await supabase.auth.getSession()
      const token = data.session?.access_token

      return {
        headers: {
          ...(options.headers ?? {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          Accept: 'text/event-stream',
        },
        body: {
          threadId,
          messages: mapUiMessagesToBackendMessages(options.messages),
        },
      }
    },
  })
}
