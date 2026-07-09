import { useState } from 'react'
import { Check, Undo2, PlayCircle } from 'lucide-react'
import { PageHeader, Card, AutonomyBadge, StatusPill, Button, Table, Td } from '../components/ui'
import { ACTIONS, PROVENANCE_TRACE } from '../data/mock'
import { cn } from '../lib/utils'

export default function Provenance() {
  const [selectedId, setSelectedId] = useState('ACT-2210')
  const [rollbackAsk, setRollbackAsk] = useState(false)
  const [rolledBack, setRolledBack] = useState(false)
  const selected = ACTIONS.find((a) => a.id === selectedId)!

  return (
    <div>
      <PageHeader
        title="Provenance / Audit Viewer"
        subtitle="Every autonomous decision is replayable: what fired, why, what it checked, and how to undo it. The audit log is append-only."
      />

      <div className="grid gap-4 xl:grid-cols-5">
        {/* Action ledger */}
        <Card title="Action ledger" className="xl:col-span-3" padded={false}>
          <Table head={['Action', 'Target', 'Level', 'Blast radius', 'Status', 'Time']}>
            {ACTIONS.map((a) => (
              <tr
                key={a.id}
                onClick={() => { setSelectedId(a.id); setRollbackAsk(false); setRolledBack(false) }}
                className={cn('cursor-pointer transition-colors hover:bg-surface-2/60', selectedId === a.id && 'bg-surface-2')}
              >
                <Td>
                  <div className="font-mono text-xs font-semibold">{a.id}</div>
                  <div className="font-mono text-[13px] text-accent-bright">{a.type}</div>
                </Td>
                <Td className="max-w-44 truncate font-mono text-xs text-ink-2">{a.target}</Td>
                <Td><AutonomyBadge level={a.level} /></Td>
                <Td>
                  <span className={cn(
                    'font-data text-xs font-semibold',
                    a.blastRadius < 0.3 ? 'text-status-good' : a.blastRadius < 0.6 ? 'text-status-warning' : 'text-danger',
                  )}>
                    {a.blastRadius.toFixed(2)}
                  </span>
                </Td>
                <Td><StatusPill status={a.status} /></Td>
                <Td className="font-mono text-xs whitespace-nowrap text-ink-3">{a.time}</Td>
              </tr>
            ))}
          </Table>
        </Card>

        {/* Decision replay */}
        <Card
          title={`Decision replay · ${selected.id}`}
          className="xl:col-span-2"
          action={<span className="inline-flex items-center gap-1 font-mono text-[11px] text-ink-3"><PlayCircle size={12} aria-hidden /> immutable record</span>}
        >
          <div className="mb-3 rounded-md border border-border-subtle bg-bg px-3 py-2.5">
            <div className="font-mono text-sm font-semibold">{selected.type} → {selected.target}</div>
            <div className="mt-1 font-mono text-[11px] text-ink-3">rollback plan: {selected.rollback}</div>
          </div>

          {selected.id === 'ACT-2210' ? (
            <ol className="space-y-0">
              {PROVENANCE_TRACE.map((t, i) => (
                <li key={t.step} className="relative pb-4 pl-7 last:pb-0">
                  {i < PROVENANCE_TRACE.length - 1 && <span className="absolute top-4 left-[7px] h-full w-px bg-border" aria-hidden />}
                  <span className="absolute top-0.5 left-0 grid h-[15px] w-[15px] place-items-center rounded-full border border-accent bg-accent-dim">
                    <Check size={9} className="text-accent-bright" aria-hidden />
                  </span>
                  <div className="text-xs font-semibold">{t.step}</div>
                  <p className="mt-0.5 text-xs leading-relaxed text-ink-2">{t.detail}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="py-3 text-sm text-ink-3">
              Full trace stored — select <span className="font-mono">ACT-2210</span> for the worked replay example.
            </p>
          )}

          <div className="mt-4 border-t border-border-subtle pt-3.5">
            {rolledBack ? (
              <div className="rounded-md border border-info/30 bg-info/10 px-3 py-2.5 text-sm text-info">
                Rolled back. The undo is now its own provenance record (ACT-2214) — audits see both directions.
              </div>
            ) : rollbackAsk ? (
              <div className="rounded-md border border-status-warning/30 bg-status-warning/5 p-3.5">
                <p className="text-sm">Undo <span className="font-mono font-semibold">{selected.type}</span> on <span className="font-mono">{selected.target}</span>? The user's Moscow session would become valid again.</p>
                <div className="mt-2.5 flex gap-2">
                  <Button size="sm" variant="danger" onClick={() => setRolledBack(true)}>Confirm rollback</Button>
                  <Button size="sm" variant="ghost" onClick={() => setRollbackAsk(false)}>Cancel</Button>
                </div>
              </div>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setRollbackAsk(true)} disabled={selected.status !== 'executed'}>
                <Undo2 size={13} aria-hidden /> One-click rollback
              </Button>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
