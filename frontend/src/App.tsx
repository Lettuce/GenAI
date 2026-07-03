import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { AuthForm } from './components/AuthForm'
import { signOut } from './lib/api'
import { supabase } from './lib/supabase'

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
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-10">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-semibold tracking-tight">Document Copilot</h1>
          <p className="mt-2 text-sm text-slate-600">Sign in or create an account to continue.</p>
        </div>

        {session ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm text-slate-600">You are signed in.</p>
            <button
              type="button"
              onClick={() => void signOut()}
              className="mt-4 rounded bg-slate-900 px-3 py-2 text-sm text-white"
            >
              Sign out
            </button>
          </div>
        ) : (
          <AuthForm onSuccess={() => {}} />
        )}
      </div>
    </main>
  )
}

export default App
