import { useMemo } from 'react'
import { DefaultChatTransport } from 'ai'

import { getAccessToken } from '@/lib/api'
import { env } from '@/lib/env'

export function useChatTransport(threadId: string) {
  return useMemo(
    () =>
      new DefaultChatTransport({
        api: `${env.apiBaseUrl}/chat/stream`,
        headers: async () => {
          const token = await getAccessToken()
          return token ? { Authorization: `Bearer ${token}` } : {}
        },
        prepareSendMessagesRequest: ({ messages }) => ({
          body: { threadId, messages },
        }),
      }),
    [threadId],
  )
}
