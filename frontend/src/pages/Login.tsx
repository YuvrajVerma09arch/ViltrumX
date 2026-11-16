import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ShieldCheck, Loader2 } from 'lucide-react'
import { Button } from '../components/ui'
import { loginChallenge, register, type AuthPurpose } from '../lib/api'

export default function Login() {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('arjun.mehta@paykraft.in')
  const [password, setPassword] = useState('viltrumx-demo')
  const [fullName, setFullName] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  function slugify(s: string): string {
    return s
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 60)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setError('Enter a valid work email — e.g. you@company.in')
      return
    }
    if (mode === 'signup') {
      if (!fullName.trim()) {
        setError('Enter your full name')
        return
      }
      if (!tenantName.trim()) {
        setError('Enter your organisation name')
        return
      }
    }
    setError('')
    setLoading(true)
    try {
      // Step 1 only requests a code. NO token is stored here — the session is
      // created exclusively by Verify.tsx after the 6-digit code checks out.
      if (mode === 'signup') {
        await register({
          email,
          password,
          full_name: fullName.trim(),
          tenant_name: tenantName.trim(),
          tenant_slug: slugify(tenantName),
        })
      } else {
        await loginChallenge(email, password)
      }
      const purpose: AuthPurpose = mode === 'signup' ? 'signup' : 'login'
      navigate(
        `/verify?email=${encodeURIComponent(email.trim())}&purpose=${purpose}`,
        // Carry the password out of the URL: login-verify needs it, but it must
        // never appear in a query string or browser history. Verify.tsx falls
        // back to asking for it again if router state is unavailable.
        { state: mode === 'signin' ? { password } : null },
      )
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Sign-in failed — is the API running?',
      )
    } finally {
      setLoading(false)
    }
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
            <button
              type="button"
              disabled
              title="OAuth SSO is roadmap — use the email form below"
              className="rounded-md border border-border py-2.5 text-sm font-medium text-ink-3 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Google Workspace
            </button>
            <button
              type="button"
              disabled
              title="OAuth SSO is roadmap — use the email form below"
              className="rounded-md border border-border py-2.5 text-sm font-medium text-ink-3 disabled:cursor-not-allowed disabled:opacity-50"
            >
              GitHub
            </button>
          </div>
          <div className="my-5 flex items-center gap-3 text-xs text-ink-3">
            <span className="h-px flex-1 bg-border" aria-hidden /> or with email <span className="h-px flex-1 bg-border" aria-hidden />
          </div>

          <form onSubmit={submit} noValidate>
            {mode === 'signup' && (
              <>
                <div className="mb-4">
                  <label htmlFor="fullName" className="mb-1.5 block text-sm font-medium">
                    Full name <span className="text-danger">*</span>
                  </label>
                  <input
                    id="fullName"
                    type="text"
                    autoComplete="name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Arjun Mehta"
                    className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm placeholder:text-ink-3 focus:border-accent focus:outline-none"
                    required
                  />
                </div>
                <div className="mb-4">
                  <label htmlFor="tenantName" className="mb-1.5 block text-sm font-medium">
                    Organisation name <span className="text-danger">*</span>
                  </label>
                  <input
                    id="tenantName"
                    type="text"
                    value={tenantName}
                    onChange={(e) => setTenantName(e.target.value)}
                    placeholder="PayKraft Technologies"
                    className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm placeholder:text-ink-3 focus:border-accent focus:outline-none"
                    required
                  />
                  <p className="mt-1 text-xs text-ink-3">Creates your tenant slug (e.g. paykraft-technologies)</p>
                </div>
              </>
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
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm focus:border-accent focus:outline-none" />
              <p className="mt-1.5 text-xs text-ink-3">12+ characters. SSO enforcement available on the Growth plan.</p>
            </div>
            <Button type="submit" disabled={loading} className="w-full">
              {loading && <Loader2 size={15} className="animate-spin" aria-hidden />}
              {mode === 'signin' ? 'Send sign-in code' : 'Create org & send code'}
            </Button>
            <p className="mt-3 text-center text-xs text-ink-3">
              We'll email you a 6-digit code to confirm it's really you — no session is created until you enter it.
            </p>
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
