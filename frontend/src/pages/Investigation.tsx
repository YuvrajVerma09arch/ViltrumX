import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Briefcase, FileSearch, ArrowRight, Loader2 } from 'lucide-react'
import { PageHeader, Card, Badge, SeverityBadge, StatusPill, Button, Segmented, Toggle, StatTile, DataSource } from '../components/ui'
import { ATTACK_CHAIN, EVIDENCE, INCIDENTS, type Action, type ChainStep, type Incident } from '../data/mock'
import { NARRATIVE, LANG_OPTIONS, type Lang } from '../data/i18n'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'
import { cn } from '../lib/utils'

type Evidence = { id: string; kind: string; source: string; excerpt: string }
type IncidentDetail = Incident & { attackChain?: ChainStep[]; evidence?: Evidence[] }

export default function Investigation() {
  const [lang, setLang] = useState<Lang>('en')
  const [founderMode, setFounderMode] = useState(false)
  const [params] = useSearchParams()
  const incidentId = params.get('incident') ?? 'INC-042'

  const detail = useApi<IncidentDetail>(
    () => endpoints.incident(incidentId),
    { ...INCIDENTS[0], attackChain: ATTACK_CHAIN, evidence: EVIDENCE as Evidence[] },
    [incidentId],
  )

  // The Explainability agent renders EN/HI/GU server-side (IndicTrans2 for the
  // Indic languages); the local i18n strings are the offline fallback.
  const narrative = useApi<typeof NARRATIVE.en>(
    () => endpoints.narrative(incidentId, lang),
    NARRATIVE[lang],
    [incidentId, lang],
  )

  const inc = detail.data
  const n = narrative.data
  const chain = inc.attackChain ?? ATTACK_CHAIN
  const evidence = inc.evidence ?? (EVIDENCE as Evidence[])

  // Founder Mode's "approve" button acts on the real pending L4 action, so the
  // founder-facing view and the analyst-facing Provenance view drive the same
  // governed lifecycle — there is no separate, cosmetic approval path.
  const actions = useApi<Action[]>(() => endpoints.actions(), [])
  const pendingL4 = actions.data.find((a) => a.status === 'proposed')
  const [deciding, setDeciding] = useState(false)
  const [decision, setDecision] = useState('')

  async function approveL4() {
    if (!pendingL4) return
    setDeciding(true)
    try {
      await endpoints.decide(pendingL4.id, 'approve')
      setDecision(`${pendingL4.id} approved — executed and written to provenance.`)
      actions.reload()
    } catch (err) {
      setDecision(err instanceof Error ? err.message : 'Could not apply the decision.')
    } finally {
      setDeciding(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Investigation Workspace"
        subtitle={<span className="font-mono">{inc.id} · {inc.title}</span>}
      >
        <DataSource live={detail.live} loading={detail.loading} />
        <SeverityBadge severity={inc.severity} />
        <StatusPill status={inc.status} />
      </PageHeader>

      <div className="grid gap-4 xl:grid-cols-5">
        {/* Attack chain timeline */}
        <Card title="Attack chain — forensic timeline" className="xl:col-span-3" padded={false}>
          <ol className="relative p-5">
            {chain.map((step, i) => (
              <li key={`${step.time}-${i}`} className="relative pb-6 pl-8 last:pb-0">
                {i < chain.length - 1 && (
                  <span className="absolute top-5 left-[9px] h-full w-px bg-border" aria-hidden />
                )}
                <span className={cn(
                  'absolute top-1 left-0 grid h-[19px] w-[19px] place-items-center rounded-full border-2 bg-surface font-mono text-[9px] font-bold',
                  step.severity === 'critical' ? 'border-status-critical text-danger' : 'border-status-serious text-status-serious',
                )}>
                  {i + 1}
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-data text-xs text-ink-3">{step.time} IST</span>
                  <h3 className="text-sm font-semibold">{step.title}</h3>
                  <Badge tone="purple">{step.mitre} · {step.mitreName}</Badge>
                </div>
                <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-2">{step.detail}</p>
              </li>
            ))}
          </ol>
          <div className="border-t border-border-subtle px-5 py-3">
            <Link to="/app/ontology" className="inline-flex items-center gap-1.5 text-xs text-accent hover:text-accent-bright">
              view this path on the ontology graph <ArrowRight size={12} aria-hidden />
            </Link>
          </div>
        </Card>

        <div className="space-y-4 xl:col-span-2">
          {/* AI narrative */}
          <Card
            title="AI narrative — Explainability agent"
            action={
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-ink-3">Founder Mode</span>
                  <Toggle checked={founderMode} onChange={setFounderMode} label="Founder Mode" />
                </div>
                <Segmented ariaLabel="Narrative language" options={LANG_OPTIONS} value={lang} onChange={setLang} />
              </div>
            }
          >
            <p className={cn('text-sm leading-relaxed', founderMode ? 'text-ink' : 'text-ink-2')}>
              {founderMode ? n.founder : n.technical}
            </p>

            {founderMode && (
              <>
                <div className="mt-4 grid grid-cols-2 gap-2.5">
                  {n.impact.map((tile) => (
                    <StatTile key={tile.label} label={tile.label} value={<span className="text-lg">{tile.value}</span>} hint={tile.hint} tone="accent" />
                  ))}
                </div>
                <div className="mt-4 rounded-md border border-status-warning/30 bg-status-warning/5 p-3.5">
                  <p className="text-sm font-medium">{n.decision}</p>
                  {decision ? (
                    <p className="mt-2.5 rounded-md border border-info/30 bg-info/10 px-3 py-2 text-sm text-info">
                      {decision}
                    </p>
                  ) : (
                    <div className="mt-2.5 flex gap-2">
                      <Button size="sm" disabled={!pendingL4 || deciding} onClick={approveL4}>
                        {deciding && <Loader2 size={13} className="animate-spin" aria-hidden />}
                        {pendingL4 ? `Approve ${pendingL4.type} (${pendingL4.level})` : 'No L4 pending'}
                      </Button>
                      <Link to="/app/provenance">
                        <Button size="sm" variant="outline">Review the decision trace</Button>
                      </Link>
                    </div>
                  )}
                </div>
              </>
            )}
            <p className="mt-3 border-t border-border-subtle pt-2.5 font-mono text-[10px] text-ink-3">
              grounded on ontology snapshot 03:33:02 · rendered via IndicTrans2 · Critic-verified 0.96
            </p>
          </Card>

          {/* Evidence locker */}
          <Card title="Evidence locker" padded={false}>
            <ul className="divide-y divide-border-subtle">
              {evidence.map((ev) => (
                <li key={ev.id} className="px-4 py-3">
                  <div className="flex items-center gap-2 text-xs">
                    <FileSearch size={13} className="shrink-0 text-ink-3" aria-hidden />
                    <span className="font-semibold">{ev.kind}</span>
                    <span className="text-ink-3">· {ev.source}</span>
                  </div>
                  <code className="mt-1.5 block overflow-x-auto rounded bg-bg px-2.5 py-1.5 font-mono text-[11px] text-ink-2">
                    {ev.excerpt}
                  </code>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Case detail">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
              <dt className="text-ink-3">Primary entity</dt><dd className="font-mono text-xs">{inc.entity}</dd>
              <dt className="text-ink-3">MITRE techniques</dt>
              <dd className="flex flex-wrap gap-1">{inc.mitre.map((m) => <Badge key={m} tone="purple">{m}</Badge>)}</dd>
              <dt className="text-ink-3">Similar precedent</dt>
              <dd className="text-xs text-ink-2">INC-041 (Qdrant recall, 0.83 sim)</dd>
              <dt className="text-ink-3">Assigned</dt>
              <dd className="inline-flex items-center gap-1.5 text-xs"><Briefcase size={12} aria-hidden /> Digital Detective + you</dd>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  )
}
