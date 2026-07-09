import { lazy, Suspense } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ShieldCheck, Network, IndianRupee, Languages, ServerCog, GitBranch, ArrowRight, Crown,
} from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Spotlight } from '@/components/ui/spotlight'
import { CursorSpotlight } from '@/components/ui/cursor-spotlight'
import { SplineScene } from '@/components/ui/splite'
import { LiquidButton } from '@/components/ui/liquid-glass-button'

// three.js-based backdrops stay out of the main bundle — only the landing pays
const DottedSurface = lazy(() =>
  import('@/components/ui/dotted-surface').then((m) => ({ default: m.DottedSurface })),
)
const WebGLShader = lazy(() =>
  import('@/components/ui/web-gl-shader').then((m) => ({ default: m.WebGLShader })),
)

const PILLARS = [
  { icon: Network, title: 'Ontology-grounded autonomy', desc: 'Decisions are governed actions on a typed graph of your world — every one with preconditions, blast radius, rollback, and provenance.' },
  { icon: Crown, title: 'Business-criticality grounding', desc: 'You tag the payments DB as a crown jewel once; every autonomous decision is weighted by what it actually costs you.' },
  { icon: ShieldCheck, title: 'India-first compliance', desc: 'DPDP Act evidence packs, CERT-In 6-hour incident reports, RBI framework mapping — generated natively, not bolted on.' },
  { icon: Languages, title: 'Speaks your language', desc: 'Every investigation renders in English, हिंदी, or ગુજરાતી. Founder Mode explains impact in rupees, not CVE scores.' },
  { icon: GitBranch, title: 'Proven every night', desc: 'A purple-team loop attacks your own tenant nightly and scores the defense. Trust is earned with evidence, not promised.' },
  { icon: IndianRupee, title: 'Priced for the buyer', desc: 'INR pricing, GST invoicing, UPI autopay, self-serve onboarding in under 10 minutes. No six-figure annual contract.' },
]

const TERMINAL_LINES = [
  { t: '03:11:02', s: 'detect', m: 'impossible travel · bengaluru → moscow · anomaly 0.94' },
  { t: '03:29:41', s: 'invest', m: 'attack chain assembled · 5 steps · 2 crown jewels at risk' },
  { t: '03:30:58', s: 'critic', m: 'finding survives adversarial review · confidence 0.96' },
  { t: '03:31:04', s: 'action', m: 'revoke_session executed (L2) · rollback plan stored' },
  { t: '03:31:12', s: 'action', m: 'block_ip executed (L3) · auto-reverts in 60 min' },
  { t: '03:33:00', s: 'report', m: 'CERT-In draft ready · 5h 27m on the clock · EN/HI/GU' },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="min-h-dvh">
      {/* Fixed page backdrop — sits at -z-10, above the html background */}
      <Suspense fallback={null}>
        <DottedSurface />
      </Suspense>

      {/* Nav */}
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
            <path d="M16 2 L28 7 V15 C28 22.5 23 28 16 30 C9 28 4 22.5 4 15 V7 Z" fill="none" stroke="var(--color-accent)" strokeWidth="2" />
            <path d="M10.5 11 L16 21.5 L21.5 11" fill="none" stroke="var(--color-accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="font-mono text-lg font-bold">Viltrum<span className="text-accent">X</span></span>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/login" className="rounded-md px-4 py-2 text-sm text-ink-2 hover:text-ink">Sign in</Link>
          <Link to="/login" className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg transition-colors hover:bg-accent-bright">
            Start free
          </Link>
        </div>
      </nav>

      {/* Hero — spotlight card with Spline robot */}
      <header className="mx-auto max-w-6xl px-6 pt-6">
        <Card className="relative h-auto overflow-hidden bg-surface/70 backdrop-blur md:h-[560px]">
          <Spotlight className="-top-40 left-0 md:-top-20 md:left-60" fill="#3fb950" />
          <div className="flex h-full flex-col md:flex-row">
            {/* Left: copy */}
            <motion.div
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
              className="relative z-10 flex flex-1 flex-col justify-center p-8 md:p-12"
            >
              <p className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-border bg-bg/70 px-3 py-1 font-mono text-xs text-ink-2">
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
                The Security Decision OS for India&apos;s startup economy
              </p>
              <h1 className="font-mono text-4xl leading-tight font-bold tracking-tight md:text-5xl">
                <span className="bg-gradient-to-b from-ink to-ink-3 bg-clip-text text-transparent">
                  Most tools display alerts.
                </span>
                <br />
                <span className="text-accent">ViltrumX makes governed decisions.</span>
              </h1>
              <p className="mt-5 max-w-lg text-lg text-ink-2">
                An autonomous SOC that models your startup as a living digital twin, neutralizes
                threats with auditable, reversible actions — and explains every decision in your
                language, in rupees.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-4">
                <Link
                  to="/login"
                  className="inline-flex h-12 items-center gap-2 rounded-full bg-accent px-7 font-semibold text-bg transition-colors hover:bg-accent-bright"
                >
                  Onboard in 10 minutes <ArrowRight size={16} aria-hidden />
                </Link>
                <LiquidButton
                  size="xl"
                  className="rounded-full border border-border font-semibold text-ink"
                  onClick={() => navigate('/app')}
                >
                  View live demo
                </LiquidButton>
              </div>
              <div className="mt-8 flex items-center gap-2">
                <span className="relative flex h-3 w-3 items-center justify-center" aria-hidden>
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
                </span>
                <p className="font-mono text-xs text-accent-bright">8/8 agents nominal · demo tenant live now</p>
              </div>
            </motion.div>

            {/* Right: 3D scene (streams from prod.spline.design — needs network) */}
            <div className="relative hidden min-h-[560px] flex-1 md:block">
              <SplineScene
                scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
                className="h-full w-full"
              />
            </div>
          </div>
        </Card>
      </header>

      {/* Terminal — last night, while you slept */}
      <section className="scanlines relative mx-auto max-w-6xl px-6 py-16">
        <motion.div
          initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }}
          className="relative mx-auto max-w-3xl overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
        >
          <CursorSpotlight size={340} />
          <div className="flex items-center gap-1.5 border-b border-border-subtle px-4 py-2.5">
            <span className="h-2.5 w-2.5 rounded-full bg-status-critical/70" aria-hidden />
            <span className="h-2.5 w-2.5 rounded-full bg-status-warning/70" aria-hidden />
            <span className="h-2.5 w-2.5 rounded-full bg-status-good/70" aria-hidden />
            <span className="ml-3 font-mono text-xs text-ink-3">viltrumx · last night, while you slept</span>
          </div>
          <div className="space-y-1.5 p-4 font-mono text-xs md:text-[13px]">
            {TERMINAL_LINES.map((l, i) => (
              <motion.div
                key={l.t}
                initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ delay: 0.2 + i * 0.15 }}
                className="flex gap-3"
              >
                <span className="text-ink-3">{l.t}</span>
                <span className={l.s === 'action' ? 'text-accent' : l.s === 'report' ? 'text-info' : 'text-ink-2'}>
                  [{l.s}]
                </span>
                <span className="text-ink">{l.m}</span>
              </motion.div>
            ))}
            <motion.div
              initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ delay: 1.3 }}
              className="pt-1 text-accent"
            >
              ▌ zero records exfiltrated · founder informed in हिंदी
            </motion.div>
          </div>
        </motion.div>
      </section>

      {/* Metric strip */}
      <section className="border-y border-border bg-surface/50">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-10 text-center md:grid-cols-4">
          {[
            ['97%', 'alert noise suppressed'],
            ['<60 s', 'median detection time'],
            ['L1–L4', 'governed autonomy ladder'],
            ['6 hrs', 'CERT-In window — met with one click'],
          ].map(([v, k]) => (
            <div key={k}>
              <div className="font-data text-3xl font-bold text-accent">{v}</div>
              <div className="mt-1 text-sm text-ink-2">{k}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Pillars */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-center font-mono text-2xl font-bold">Built for the startup with real attack surface and zero analysts</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-ink-2">
          Seed to Series-B, 20–300 people, Google Workspace + GitHub + AWS + Razorpay — and no security team.
        </p>
        <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PILLARS.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
              transition={{ delay: (i % 3) * 0.08 }}
              className="rounded-lg border border-border bg-surface p-5 transition-colors hover:border-ink-3"
            >
              <p.icon size={20} className="text-accent" aria-hidden />
              <h3 className="mt-3 font-mono text-sm font-semibold">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-2">{p.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-border bg-surface/40">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="text-center font-mono text-2xl font-bold">Three steps to a governed SOC</h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {[
              ['01', 'Connect your world', 'OAuth into Workspace, GitHub, AWS, Razorpay. The ontology builds itself — you just tag your crown jewels.'],
              ['02', 'Set the autonomy dial', 'Per action type, per criticality: from “always ask me” to “act and tell me.” Every tenant starts conservative and earns trust.'],
              ['03', 'Sleep. It proves itself.', 'Agents detect, investigate, verify, and respond all night. The purple team attacks you nightly and publishes the score.'],
            ].map(([n, t, d]) => (
              <div key={n} className="relative">
                <div className="font-data text-4xl font-bold text-accent-dim">{n}</div>
                <h3 className="mt-2 font-mono font-semibold">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-2">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA — neon shader banner */}
      <section className="relative overflow-hidden border-t border-border">
        <Suspense fallback={null}>
          <WebGLShader />
        </Suspense>
        <div className="relative z-10 mx-auto max-w-6xl px-6 py-28 text-center">
          <h2 className="font-mono text-3xl font-bold md:text-4xl">
            Grounded in your world. Proven every night.
            <br /><span className="text-accent">Understood in your language.</span>
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-ink-2">
            Self-serve onboarding, INR pricing, and a defense readiness score you can show your board.
          </p>
          <div className="mt-9 flex justify-center">
            <LiquidButton
              size="xl"
              className="rounded-full border border-accent/40 font-semibold text-accent-bright"
              onClick={() => navigate('/login')}
            >
              Start free — ₹0 for 14 days
            </LiquidButton>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-6 gap-y-2 px-6 py-10 font-mono text-xs text-ink-3">
        <span>© 2026 ViltrumX</span>
        <span>Made in India 🇮🇳</span>
        <span>DPDP-ready · CERT-In-aware · data stays in ap-south-1</span>
        <span className="inline-flex items-center gap-1"><ServerCog size={12} aria-hidden /> sovereign self-hosted inference available</span>
      </footer>
    </div>
  )
}
