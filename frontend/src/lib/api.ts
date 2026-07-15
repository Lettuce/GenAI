import { ApiError, requestJson } from './http'
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
