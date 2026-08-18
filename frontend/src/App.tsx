import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import { signOut } from './lib/api'
import { ChatPage } from './pages/chat/ChatPage'
import { LoginPage } from './pages/LoginPage'
import { supabase } from './lib/supabase'

interface ProtectedRouteProps {
  session: Session | null
  children: ReactNode
}

function ProtectedRoute({ session, children }: ProtectedRouteProps) {
  if (!session) {
    return <Navigate to="/login" replace />
  }
  return children
}

function AppHeader({ session }: { session: Session | null }) {
  const navigate = useNavigate()

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  if (!session) {
    return null
  }

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <img src="/log.png" alt="Document Copilot logo" className="h-8 w-8 object-contain" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-slate-900">Document Copilot</h1>
          <p className="text-xs text-slate-500">AI research assistant for SEC filings, company analysis, and cited source-grounded answers.</p>
        </div>
      </div>
      <button type="button" onClick={() => void handleSignOut()} className="rounded bg-slate-900 px-3 py-2 text-sm text-white">
        Sign out
      </button>
    </header>
  )
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      setLoading(false)
    })

    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">Loading…</div>
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader session={session} />
      <Routes>
        <Route path="/login" element={<LoginPage session={session} />} />
        <Route
          path="/chat"
          element={
            <ProtectedRoute session={session}>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat/:threadId"
          element={
            <ProtectedRoute session={session}>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to={session ? '/chat' : '/login'} replace />} />
      </Routes>
    </div>
  )
}

export default App
