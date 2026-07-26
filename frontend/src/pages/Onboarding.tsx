import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Crown, Plug } from 'lucide-react'
import { PageHeader, Card, Button, StatusPill, CriticalityBadge, Segmented, DataSource } from '../components/ui'
import { CONNECTORS } from '../data/mock'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'
import { cn, type Criticality } from '../lib/utils'

const STEPS = ['Org profile', 'Connect sources', 'Tag crown jewels', 'Autonomy defaults']

const JEWEL_CANDIDATES: { name: string; kind: string; initial: Criticality }[] = [
  { name: 's3://customers-db-backups', kind: 'S3 · nightly PII dumps', initial: 'crown-jewel' },
  { name: 'rds/payments-db', kind: 'RDS · production ledger', initial: 'crown-jewel' },
  { name: 'Razorpay settlement account', kind: 'SaaS · payment rail', initial: 'crown-jewel' },
  { name: 'paykraft-core', kind: 'Repo · payments monolith', initial: 'high' },
  { name: 'Google Workspace admin', kind: 'SaaS · identity root', initial: 'high' },
]

export default function Onboarding() {
  const [step, setStep] = useState(1)
  const connectors = useApi<typeof CONNECTORS>(() => endpoints.connectors(), CONNECTORS)
  const [connected, setConnected] = useState<Record<string, boolean>>({})

  // Seed local toggle state from whatever the server already has connected.
  useEffect(() => {
    setConnected(
      Object.fromEntries(connectors.data.map((c) => [c.id, c.status === 'connected'])),
    )
  }, [connectors.data])

  // Persist the connection so it survives a reload — the wizard is a real
  // setup flow, not a slideshow.
  async function connect(id: string) {
    setConnected((prev) => ({ ...prev, [id]: true }))
    try {
      await endpoints.connect(id)
    } catch {
      setConnected((prev) => ({ ...prev, [id]: false }))
    }
  }

  const [jewels, setJewels] = useState<Record<string, Criticality>>(
    Object.fromEntries(JEWEL_CANDIDATES.map((j) => [j.name, j.initial])),
  )
  const [posture, setPosture] = useState<'conservative' | 'balanced' | 'assertive'>('balanced')
  const navigate = useNavigate()

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Onboarding & Integrations"
        subtitle="Connect your world in under 10 minutes. The ontology builds itself from what you plug in."
      >
        <DataSource live={connectors.live} loading={connectors.loading} />
      </PageHeader>

      {/* Stepper */}
      <ol className="mb-8 flex items-center gap-2" aria-label="Onboarding progress">
        {STEPS.map((s, i) => {
          const n = i + 1
          const state = n < step ? 'done' : n === step ? 'current' : 'todo'
          return (
            <li key={s} className="flex flex-1 items-center gap-2">
              <span className={cn(
                'grid h-7 w-7 shrink-0 place-items-center rounded-full border font-mono text-xs font-semibold',
                state === 'done' && 'border-accent bg-accent-dim text-accent-bright',
                state === 'current' && 'border-accent text-accent',
                state === 'todo' && 'border-border text-ink-3',
              )}>
                {state === 'done' ? <Check size={13} aria-hidden /> : n}
              </span>
              <span className={cn('hidden text-xs sm:block', state === 'current' ? 'font-medium text-ink' : 'text-ink-3')}>{s}</span>
              {n < STEPS.length && <span className="h-px flex-1 bg-border" aria-hidden />}
            </li>
          )
        })}
      </ol>

      {step === 1 && (
        <Card title="Step 1 · Org profile">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="ob-org" className="mb-1.5 block text-sm font-medium">Organisation</label>
              <input id="ob-org" defaultValue="PayKraft Technologies" className="w-full rounded-md border border-border bg-bg px-3 py-2.5 text-sm focus:border-accent focus:outline-none" />
            </div>
            <div>
              <label htmlFor="ob-industry" className="mb-1.5 block text-sm font-medium">Industry</label>
              <select id="ob-industry" defaultValue="Fintech / payments" className="w-full cursor-pointer rounded-md border border-border bg-bg px-3 py-2.5 text-sm focus:border-accent focus:outline-none">
                <option>Fintech / payments</option><option>SaaS</option><option>Healthtech</option><option>E-commerce</option><option>Other</option>
              </select>
              <p className="mt-1.5 text-xs text-ink-3">Fintech enables the RBI framework mapping automatically.</p>
            </div>
            <div>
              <label htmlFor="ob-size" className="mb-1.5 block text-sm font-medium">Team size</label>
              <select id="ob-size" defaultValue="51–100" className="w-full cursor-pointer rounded-md border border-border bg-bg px-3 py-2.5 text-sm focus:border-accent focus:outline-none">
                <option>1–20</option><option>21–50</option><option>51–100</option><option>101–300</option>
              </select>
            </div>
            <div>
              <label htmlFor="ob-region" className="mb-1.5 block text-sm font-medium">Data residency</label>
              <select id="ob-region" defaultValue="India (ap-south-1)" className="w-full cursor-pointer rounded-md border border-border bg-bg px-3 py-2.5 text-sm focus:border-accent focus:outline-none">
                <option>India (ap-south-1)</option><option>India (self-hosted inference)</option>
              </select>
            </div>
          </div>
          <div className="mt-5 flex justify-end">
            <Button onClick={() => setStep(2)}>Continue</Button>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card title="Step 2 · Connect sources">
          <ul className="space-y-2.5">
            {connectors.data.map((c) => {
              const isOn = connected[c.id]
              return (
                <li key={c.id} className="flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-bg px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="grid h-9 w-9 place-items-center rounded-md border border-border bg-surface-2 text-ink-2"><Plug size={15} aria-hidden /></span>
                    <div>
                      <div className="text-sm font-medium">{c.name}</div>
                      <div className="text-xs text-ink-3">{c.desc} · setup {c.time}</div>
                    </div>
                  </div>
                  {isOn ? (
                    <StatusPill status="connected" />
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => connect(c.id)}>
                      Connect
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
          <div className="mt-5 flex items-center justify-between">
            <p className="font-mono text-xs text-ink-3">{Object.values(connected).filter(Boolean).length} of {connectors.data.length} connected — 3 is enough to start</p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
              <Button onClick={() => setStep(3)}>Continue</Button>
            </div>
          </div>
        </Card>
      )}

      {step === 3 && (
        <Card title="Step 3 · Tag your crown jewels">
          <p className="mb-4 text-sm text-ink-2">
            <Crown size={13} className="mr-1 inline text-status-warning" aria-hidden />
            Only you know what would actually kill the company. Criticality weights every autonomous
            decision — a crown jewel never gets touched without a human.
          </p>
          <ul className="space-y-2.5">
            {JEWEL_CANDIDATES.map((j) => (
              <li key={j.name} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border-subtle bg-bg px-4 py-3">
                <div>
                  <div className="font-mono text-sm font-medium">{j.name}</div>
                  <div className="text-xs text-ink-3">{j.kind}</div>
                </div>
                <div className="flex items-center gap-3">
                  <CriticalityBadge criticality={jewels[j.name]} />
                  <Segmented
                    ariaLabel={`Criticality for ${j.name}`}
                    value={jewels[j.name]}
                    onChange={(v) => setJewels({ ...jewels, [j.name]: v })}
                    options={[
                      { value: 'low', label: 'Low' }, { value: 'medium', label: 'Med' },
                      { value: 'high', label: 'High' }, { value: 'crown-jewel', label: 'Crown' },
                    ]}
                  />
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setStep(2)}>Back</Button>
            <Button onClick={() => setStep(4)}>Continue</Button>
          </div>
        </Card>
      )}

      {step === 4 && (
        <Card title="Step 4 · Autonomy defaults">
          <p className="mb-4 text-sm text-ink-2">
            Every tenant starts conservative and earns autonomy as the nightly purple team proves the
            system. You can change any of this per action type later in the Autonomy Console.
          </p>
          <div className="space-y-2.5">
            {([
              ['conservative', 'Propose everything', 'All containment actions wait for your approval (L4). Evidence gathering only.'],
              ['balanced', 'Recommended', 'Low-blast-radius actions auto-execute with notification (L2); timed blocks self-revert (L3); anything touching a crown jewel is proposed (L4).'],
              ['assertive', 'Act first at night', 'Between 22:00–07:00 IST, medium containment auto-executes with auto-rollback. Crown jewels still require approval.'],
            ] as const).map(([id, name, desc]) => (
              <label key={id} className={cn(
                'flex cursor-pointer items-start gap-3 rounded-md border px-4 py-3 transition-colors',
                posture === id ? 'border-accent bg-accent-dim/40' : 'border-border-subtle bg-bg hover:border-border',
              )}>
                <input type="radio" name="posture" checked={posture === id} onChange={() => setPosture(id)} className="mt-1 accent-[#3fb950]" />
                <span>
                  <span className="text-sm font-semibold">{name}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-ink-2">{desc}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setStep(3)}>Back</Button>
            <Button onClick={() => navigate('/app')}>Finish — open Command Deck</Button>
          </div>
        </Card>
      )}
    </div>
  )
}
