import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Mail, ShieldCheck } from 'lucide-react'
import { Button } from '../components/ui'
import { ApiError, loginVerify, resend, verify, type AuthPurpose } from '../lib/api'

const RESEND_COOLDOWN = 30 // seconds

type VerifyAction = 'verify' | 'resend'

/** Turn backend failures into plain-English, case-specific guidance. */
function describeError(err: unknown, action: VerifyAction): string {
  const status = err instanceof ApiError ? err.status : 0
  const raw = err instanceof Error ? err.message : ''
  const msg = raw.toLowerCase()

  if (action === 'resend') {
    if (status === 429 || /too many|rate limit|wait|slow down/.test(msg))
      return 'Too many resend requests. Please wait a moment before trying again.'
    if (
      status >= 500 ||
      /send|deliver|smtp|mail|unavailable|network|failed to fetch|couldn't send/.test(msg)
    )
      return "We couldn't send the code right now. Check your connection and try again."
    return raw || "We couldn't send the code. Please try again."
  }

  // Verification errors — order matters: rate-limit and expiry bodies often
  // also contain the word "invalid", so check the specific cases first.
  if (status === 429 || /too many|attempt|rate limit|locked|try again later/.test(msg))
    return 'Too many incorrect attempts. Wait a moment, then request a new code.'
  if (status === 410 || /expired|expire|timed out|too old/.test(msg))
    return 'That code has expired. Request a new one below.'
  if (
    status === 400 ||
    status === 401 ||
    status === 403 ||
    /invalid|incorrect|wrong|mismatch|not valid|bad code/.test(msg)
  )
    return "That code isn't right. Check your email and try again."
  if (status >= 500 || /network|failed to fetch|unavailable/.test(msg))
    return "We couldn't reach the server. Check your connection and try again."
  return raw || 'Verification failed. Please try again.'
}

export default function Verify() {
  const [params] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()

  const email = (params.get('email') ?? '').trim()
  const rawPurpose = params.get('purpose')
  const purpose: AuthPurpose = rawPurpose === 'signup' ? 'signup' : 'login'
  // Password travels in router state (never the URL) because login-verify
  // re-sends it. If state is missing (e.g. a reloaded shared link), the form
  // below asks for it again instead of failing silently.
  const statePassword =
    ((location.state as { password?: string } | null)?.password ?? '').trim()

  const [code, setCode] = useState('')
  const [password, setPassword] = useState(statePassword)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  // One tick per second while the resend cooldown is active.
  useEffect(() => {
    if (cooldown <= 0) return
    const timer = window.setTimeout(() => setCooldown((s) => s - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [cooldown])

  // A verification URL without an email can't be completed — fail gracefully.
  if (!email) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-6">
        <div className="w-full max-w-sm text-center">
          <h1 className="font-mono text-2xl font-bold">Invalid verification link</h1>
          <p className="mt-2 text-sm text-ink-2">
            This link is missing the email it belongs to. Please start again from sign in.
          </p>
          <Link
            to="/login"
            className="mt-5 inline-flex cursor-pointer items-center justify-center rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-bg hover:bg-accent-bright"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setNotice('')
    if (!/^\d{6}$/.test(code)) {
      setError('Enter the 6-digit code from your email.')
      return
    }
    if (purpose === 'login' && !password) {
      setError('Enter your password again to finish signing in.')
      return
    }
    setLoading(true)
    try {
      if (purpose === 'signup') {
        await verify(email, code)
        navigate('/app/onboarding', { replace: true })
      } else {
        await loginVerify(email, password, code)
        navigate('/app', { replace: true })
      }
    } catch (err) {
      setError(describeError(err, 'verify'))
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    setError('')
    setNotice('')
    setResending(true)
    try {
      await resend(email, purpose)
      setNotice('A fresh code is on its way — it should arrive in a minute.')
      setCooldown(RESEND_COOLDOWN)
    } catch (err) {
      setError(describeError(err, 'resend'))
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* Brand panel — mirrors the login screen for a consistent flow. */}
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
            One more step.
            <span className="text-accent"> We make sure it's really you before we hand over the command deck.</span>
          </blockquote>
          <p className="mt-4 text-sm text-ink-2">— owner verification</p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-ink-3">
          <ShieldCheck size={14} aria-hidden /> Data residency ap-south-1 · DPDP-ready · SOC 2 in progress
        </div>
      </div>

      {/* Verification form */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="font-mono text-2xl font-bold">Check your email</h1>
          <p className="mt-2 text-sm text-ink-2">
            We sent a 6-digit code to <span className="font-medium text-ink">{email}</span>. Enter it below to{' '}
            {purpose === 'signup' ? 'finish setting up your org' : 'sign in'}.
          </p>

          <form onSubmit={submit} noValidate className="mt-6">
            <div className="mb-4">
              <label htmlFor="code" className="mb-1.5 block text-sm font-medium">
                Verification code <span className="text-danger">*</span>
              </label>
              <input
                id="code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => {
                  setCode(e.target.value.replace(/\D/g, '').slice(0, 6))
                  if (error) setError('')
                }}
                placeholder="000000"
                aria-invalid={!!error}
                aria-describedby={error ? 'verify-error' : undefined}
                className="w-full rounded-md border border-border bg-surface px-3 py-3 text-center font-mono text-2xl tracking-[0.5em] placeholder:text-ink-3 focus:border-accent focus:outline-none"
              />
              {error && (
                <p id="verify-error" role="alert" className="mt-1.5 text-xs text-danger">
                  {error}
                </p>
              )}
            </div>

            {purpose === 'login' && !statePassword && (
              <div className="mb-4">
                <label htmlFor="reauth-password" className="mb-1.5 block text-sm font-medium">
                  Confirm your password <span className="text-danger">*</span>
                </label>
                <input
                  id="reauth-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (error) setError('')
                  }}
                  className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm focus:border-accent focus:outline-none"
                />
                <p className="mt-1 text-xs text-ink-3">We need it once more to finish verification.</p>
              </div>
            )}

            {notice && (
              <p role="status" aria-live="polite" className="mb-4 text-xs text-accent-bright">
                {notice}
              </p>
            )}

            <Button type="submit" disabled={loading || code.length !== 6} className="w-full">
              {loading && <Loader2 size={15} className="animate-spin" aria-hidden />}
              {purpose === 'signup' ? 'Verify & create my org' : 'Verify & sign in'}
            </Button>
          </form>

          <div className="mt-5 flex items-center justify-between gap-3 text-sm">
            <button
              type="button"
              onClick={handleResend}
              disabled={resending || cooldown > 0}
              className="cursor-pointer font-medium text-accent hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
            >
              {resending ? 'Sending…' : cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend code'}
            </button>
            <Link to="/login" className="inline-flex cursor-pointer items-center gap-1 text-ink-2 hover:text-ink">
              <ArrowLeft size={14} aria-hidden /> Back to sign in
            </Link>
          </div>
          <p className="mt-4 flex items-center justify-center gap-1.5 text-center text-xs text-ink-3">
            <Mail size={13} aria-hidden /> Wrong email?{' '}
            <Link to="/login" className="font-medium text-accent hover:text-accent-bright">
              Use a different address
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
