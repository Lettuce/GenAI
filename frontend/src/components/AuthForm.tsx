import { useState } from 'react'
import type { FormEvent } from 'react'
import { signIn, signUp } from '../lib/api'

interface AuthFormProps {
  onSuccess?: () => void
}

export function AuthForm({ onSuccess }: AuthFormProps) {
  const [mode, setMode] = useState<'sign-in' | 'sign-up'>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')

    try {
      if (mode === 'sign-up') {
        const result = await signUp(email, password)
        if (result.user?.identities?.length === 0) {
          setMessage('This email is already registered. Please sign in instead.')
        } else {
          setMessage('Sign-up successful. Check your inbox to confirm the email.')
        }
      } else {
        await signIn(email, password)
        setMessage('Signed in successfully.')
        onSuccess?.()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex gap-2">
        <button
          type="button"
          className={`rounded-full px-3 py-2 text-sm ${mode === 'sign-in' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}
          onClick={() => setMode('sign-in')}
        >
          Sign in
        </button>
        <button
          type="button"
          className={`rounded-full px-3 py-2 text-sm ${mode === 'sign-up' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}
          onClick={() => setMode('sign-up')}
        >
          Sign up
        </button>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium">Email</label>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-500"
        />
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium">Password</label>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          minLength={6}
          className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-500"
        />
      </div>

      <button type="submit" disabled={loading} className="w-full rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-60">
        {loading ? 'Working…' : mode === 'sign-up' ? 'Create account' : 'Sign in'}
      </button>

      {message ? <p className="text-sm text-emerald-600">{message}</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
    </form>
  )
}
