import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ShieldCheck, Network, IndianRupee, Languages, ServerCog, GitBranch, ArrowRight, Crown,
} from 'lucide-react'
import { lazy, Suspense } from 'react'

// Lazy: keeps three.js (~500 KB) out of the main bundle — only the landing pays for it
const DottedSurface = lazy(() =>
  import('@/components/ui/dotted-surface').then((m) => ({ default: m.DottedSurface })),
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
  return (
    // no bg on this wrapper: an opaque background here would paint over the
    // -z-10 canvas — the body's bg-bg (same color) shows through instead
    <div className="min-h-dvh">
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

      {/* Hero */}
      <header className="scanlines relative mx-auto max-w-6xl px-6 pt-16 pb-20 text-center">
        <motion.div className="relative" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <p className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 font-mono text-xs text-ink-2">
            <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            The Security Decision OS for India&apos;s startup economy
          </p>
          <h1 className="mx-auto max-w-3xl font-mono text-4xl leading-tight font-bold tracking-tight md:text-5xl">
            Most tools display alerts.
            <br />
            <span className="text-accent">ViltrumX makes governed decisions.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-2">
            An autonomous SOC that models your startup as a living digital twin, neutralizes threats
            with auditable, reversible actions — and explains every decision in your language, in rupees.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Link to="/login" className="inline-flex items-center gap-2 rounded-md bg-accent px-6 py-3 font-semibold text-bg transition-colors hover:bg-accent-bright">
              Onboard in 10 minutes <ArrowRight size={16} aria-hidden />
            </Link>
            <Link to="/app" className="rounded-md border border-border px-6 py-3 font-medium text-ink-2 transition-colors hover:border-ink-3 hover:text-ink">
              View live demo
            </Link>
          </div>
        </motion.div>

        {/* Terminal window */}
        <motion.div
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }}
          className="mx-auto mt-14 max-w-3xl overflow-hidden rounded-xl border border-border bg-surface text-left shadow-2xl"
        >
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
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 + i * 0.18 }}
                className="flex gap-3"
              >
                <span className="text-ink-3">{l.t}</span>
                <span className={l.s === 'action' ? 'text-accent' : l.s === 'report' ? 'text-info' : 'text-ink-2'}>
                  [{l.s}]
                </span>
                <span className="text-ink">{l.m}</span>
              </motion.div>
            ))}
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }} className="pt-1 text-accent">
              ▌ zero records exfiltrated · founder informed in हिंदी
            </motion.div>
          </div>
        </motion.div>
      </header>

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

      {/* CTA + footer */}
      <footer className="mx-auto max-w-6xl px-6 py-20 text-center">
        <h2 className="font-mono text-3xl font-bold">
          Grounded in your world. Proven every night.
          <br /><span className="text-accent">Understood in your language.</span>
        </h2>
        <Link to="/login" className="mt-8 inline-flex items-center gap-2 rounded-md bg-accent px-8 py-3.5 font-semibold text-bg transition-colors hover:bg-accent-bright">
          Start free — ₹0 for 14 days <ArrowRight size={16} aria-hidden />
        </Link>
        <div className="mt-14 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 border-t border-border-subtle pt-8 font-mono text-xs text-ink-3">
          <span>© 2026 ViltrumX</span>
          <span>Made in India 🇮🇳</span>
          <span>DPDP-ready · CERT-In-aware · data stays in ap-south-1</span>
          <span className="inline-flex items-center gap-1"><ServerCog size={12} aria-hidden /> sovereign self-hosted inference available</span>
        </div>
      </footer>
    </div>
  )
}
