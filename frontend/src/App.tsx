import { useState } from 'react'
import { Button } from '@/components/ui/button'

function App() {
  const [count, setCount] = useState(0)

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 px-6 py-10 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-[calc(100vh-80px)] max-w-4xl flex-col justify-center gap-8">
        <section className="rounded-3xl border border-slate-200 bg-white/90 p-8 shadow-xl shadow-slate-900/5 backdrop-blur dark:border-slate-700 dark:bg-slate-900/80">
          <h1 className="text-4xl font-semibold tracking-tight">Get started</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600 dark:text-slate-300">
            Edit <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-sm text-slate-800 dark:bg-slate-800 dark:text-slate-100">src/App.tsx</code> and save to test HMR.
          </p>
          <div className="mt-6">
            <Button onClick={() => setCount((count) => count + 1)}>
              Count is {count}
            </Button>
          </div>
        </section>
      </div>
    </main>
  )
}

export default App
