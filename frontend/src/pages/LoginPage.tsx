import { Navigate } from 'react-router-dom'
import type { Session } from '@supabase/supabase-js'

import { AuthForm } from '../components/AuthForm'

interface LoginPageProps {
  session: Session | null
}

export function LoginPage({ session }: LoginPageProps) {
  if (session) {
    return <Navigate to="/chat" replace />
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-10">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full border border-slate-200 bg-white shadow-sm">
            <img src="/favicon.svg" alt="Document Copilot logo" className="h-11 w-11 object-contain" />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Document Copilot</h1>
          <p className="mt-2 text-sm text-slate-600">Sign in or create an account to continue.</p>
        </div>
        <AuthForm onSuccess={() => {}} />
      </div>
    </main>
  )
}
