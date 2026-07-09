import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ShieldCheck, Loader2 } from 'lucide-react'
import { Button } from '../components/ui'

export default function Login() {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setError('Enter a valid work email — e.g. you@company.in')
      return
    }
    setError('')
    setLoading(true)
    setTimeout(() => navigate(mode === 'signup' ? '/app/onboarding' : '/app'), 700)
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* Brand panel */}
      <div className="scanlines relative hidden flex-col justify-between border-r border-border bg-surface p-10 lg:flex">
        <Link to="/" className="flex items-center gap-2.5">
          <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
            <path d="M16 2 L28 7 V15 C28 22.5 23 28 16 30 C9 28 4 22.5 4 15 V7 Z" fill="none" stroke="var(--color-accent)" strokeWidth="2" />
            <path d="M10.5 11 L16 21.5 L21.5 11" fill="none" stroke="var(--color-accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="font-mono text-xl font-bold">Viltrum<span className="text-accent">X</span></span>
        </Link>
        <div>
          <blockquote className="max-w-md font-mono text-2xl leading-snug font-semibold">
            “Someone tried to steal our customer database at 3 AM.
            <span className="text-accent"> I read what happened in Hindi, over chai, after it was already stopped.</span>”
          </blockquote>
          <p className="mt-4 text-sm text-ink-2">— every founder ViltrumX is built for</p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-ink-3">
          <ShieldCheck size={14} aria-hidden /> Data residency ap-south-1 · DPDP-ready · SOC 2 in progress
        </div>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="font-mono text-2xl font-bold">
            {mode === 'signin' ? 'Welcome back' : 'Create your org'}
          </h1>
          <p className="mt-2 text-sm text-ink-2">
            {mode === 'signin' ? 'Sign in to your security command deck.' : 'Self-serve onboarding — protected in under 10 minutes.'}
          </p>

          <div className="mt-6 grid grid-cols-2 gap-2">
            <button className="cursor-pointer rounded-md border border-border py-2.5 text-sm font-medium transition-colors hover:bg-surface-2">
              Google Workspace
            </button>
            <button className="cursor-pointer rounded-md border border-border py-2.5 text-sm font-medium transition-colors hover:bg-surface-2">
              GitHub
            </button>
          </div>
          <div className="my-5 flex items-center gap-3 text-xs text-ink-3">
            <span className="h-px flex-1 bg-border" aria-hidden /> or with email <span className="h-px flex-1 bg-border" aria-hidden />
          </div>

          <form onSubmit={submit} noValidate>
            {mode === 'signup' && (
              <div className="mb-4">
                <label htmlFor="org" className="mb-1.5 block text-sm font-medium">Organisation name</label>
                <input id="org" type="text" placeholder="PayKraft Technologies"
                  className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm placeholder:text-ink-3 focus:border-accent focus:outline-none" />
              </div>
            )}
            <div className="mb-4">
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium">Work email <span className="text-danger">*</span></label>
              <input
                id="email" type="email" autoComplete="email" value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.in"
                aria-invalid={!!error}
                className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm placeholder:text-ink-3 focus:border-accent focus:outline-none"
              />
              {error && <p role="alert" className="mt-1.5 text-xs text-danger">{error}</p>}
            </div>
            <div className="mb-5">
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium">Password <span className="text-danger">*</span></label>
              <input id="password" type="password" autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm focus:border-accent focus:outline-none" />
              <p className="mt-1.5 text-xs text-ink-3">12+ characters. SSO enforcement available on the Growth plan.</p>
            </div>
            <Button type="submit" disabled={loading} className="w-full">
              {loading && <Loader2 size={15} className="animate-spin" aria-hidden />}
              {mode === 'signin' ? 'Sign in' : 'Create org & connect sources'}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-2">
            {mode === 'signin' ? 'New to ViltrumX?' : 'Already have an org?'}{' '}
            <button
              onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setError('') }}
              className="cursor-pointer font-medium text-accent hover:text-accent-bright"
            >
              {mode === 'signin' ? 'Create your org' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
