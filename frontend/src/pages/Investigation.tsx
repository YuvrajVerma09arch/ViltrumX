import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Briefcase, FileSearch, ArrowRight } from 'lucide-react'
import { PageHeader, Card, Badge, SeverityBadge, StatusPill, Button, Segmented, Toggle, StatTile } from '../components/ui'
import { ATTACK_CHAIN, EVIDENCE, INCIDENTS } from '../data/mock'
import { NARRATIVE, LANG_OPTIONS, type Lang } from '../data/i18n'
import { cn } from '../lib/utils'

export default function Investigation() {
  const [lang, setLang] = useState<Lang>('en')
  const [founderMode, setFounderMode] = useState(false)
  const n = NARRATIVE[lang]
  const inc = INCIDENTS[0]

  return (
    <div>
      <PageHeader
        title="Investigation Workspace"
        subtitle={<span className="font-mono">{inc.id} · {inc.title}</span>}
      >
        <SeverityBadge severity={inc.severity} />
        <StatusPill status={inc.status} />
      </PageHeader>

      <div className="grid gap-4 xl:grid-cols-5">
        {/* Attack chain timeline */}
        <Card title="Attack chain — forensic timeline" className="xl:col-span-3" padded={false}>
          <ol className="relative p-5">
            {ATTACK_CHAIN.map((step, i) => (
              <li key={step.time} className="relative pb-6 pl-8 last:pb-0">
                {i < ATTACK_CHAIN.length - 1 && (
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
                  <div className="mt-2.5 flex gap-2">
                    <Button size="sm">Approve freeze (L4)</Button>
                    <Button size="sm" variant="outline">Ask the Detective more</Button>
                  </div>
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
              {EVIDENCE.map((ev) => (
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
