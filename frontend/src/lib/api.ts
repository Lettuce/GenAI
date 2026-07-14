import { ApiError, requestJson, requestStream } from './http'
import { supabase } from './supabase'

export { ApiError }

export interface ChatThread {
  id: string
  title: string | null
  created_at: string
}

export interface ChatMessage {
  id: string
  thread_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface StreamMessage {
  role: 'user' | 'assistant'
  content: string
}

export async function signUp(email: string, password: string) {
  const { data, error } = await supabase.auth.signUp({ email, password })
  if (error) throw error
  return data
}

export async function signIn(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password })
  if (error) throw error
  return data
}

export async function signOut() {
  const { error } = await supabase.auth.signOut()
  if (error) throw error
}

export async function getAccessToken() {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

export async function listThreads() {
  return requestJson<ChatThread[]>('/chat/threads')
}

export async function createThread(title?: string) {
  return requestJson<ChatThread>('/chat/threads', {
    method: 'POST',
    body: JSON.stringify({ title: title ?? null }),
  })
}

export async function listThreadMessages(threadId: string) {
  return requestJson<ChatMessage[]>(`/chat/threads/${threadId}/messages`)
}

export async function streamChat(
  threadId: string,
  messages: StreamMessage[],
  onDelta: (delta: string) => void,
) {
  const response = await requestStream('/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/plain',
    },
    body: JSON.stringify({
      threadId,
      messages,
    }),
  })

  const stream = response.body
  if (!stream) {
    throw new ApiError('No response stream returned')
  }

  const reader = stream.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    onDelta(decoder.decode(value, { stream: true }))
  }
}
