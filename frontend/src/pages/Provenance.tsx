import { useEffect, useState } from 'react'
import { Check, X, Undo2, PlayCircle, Loader2 } from 'lucide-react'
import { PageHeader, Card, AutonomyBadge, StatusPill, Button, Table, Td, DataSource } from '../components/ui'
import { ACTIONS, PROVENANCE_TRACE, type Action } from '../data/mock'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'
import { cn } from '../lib/utils'

type TraceStep = { step: string; detail: string; ok: boolean }

export default function Provenance() {
  const actions = useApi<Action[]>(() => endpoints.actions(), ACTIONS)
  const [selectedId, setSelectedId] = useState('')
  const [rollbackAsk, setRollbackAsk] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  // Default to the first action once the ledger loads (ids are server-assigned,
  // so we can't hardcode one and expect it to exist).
  useEffect(() => {
    if (!selectedId && actions.data.length) setSelectedId(actions.data[0].id)
  }, [actions.data, selectedId])

  const selected = actions.data.find((a) => a.id === selectedId) ?? actions.data[0]

  const trace = useApi<TraceStep[]>(
    () => (selectedId ? endpoints.actionTrace(selectedId) : Promise.reject(new Error('no selection'))),
    PROVENANCE_TRACE as TraceStep[],
    [selectedId],
  )

  function select(id: string) {
    setSelectedId(id)
    setRollbackAsk(false)
    setNotice('')
  }

  async function run(fn: () => Promise<unknown>, message: string) {
    setBusy(true)
    try {
      await fn()
      setNotice(message)
      setRollbackAsk(false)
      actions.reload()
      trace.reload()
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'Action failed.')
    } finally {
      setBusy(false)
    }
  }

  if (!selected) {
    return (
      <div>
        <PageHeader title="Provenance / Audit Viewer" subtitle="No actions recorded yet." />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Provenance / Audit Viewer"
        subtitle="Every autonomous decision is replayable: what fired, why, what it checked, and how to undo it. The audit log is append-only."
      >
        <DataSource live={actions.live} loading={actions.loading} />
      </PageHeader>

      <div className="grid gap-4 xl:grid-cols-5">
        {/* Action ledger */}
        <Card title="Action ledger" className="xl:col-span-3" padded={false}>
          <Table head={['Action', 'Target', 'Level', 'Blast radius', 'Status', 'Time']}>
            {actions.data.map((a) => (
              <tr
                key={a.id}
                onClick={() => select(a.id)}
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

          <ol className="space-y-0">
            {trace.data.map((t, i) => (
              <li key={`${t.step}-${i}`} className="relative pb-4 pl-7 last:pb-0">
                {i < trace.data.length - 1 && <span className="absolute top-4 left-[7px] h-full w-px bg-border" aria-hidden />}
                <span className={cn(
                  'absolute top-0.5 left-0 grid h-[15px] w-[15px] place-items-center rounded-full border',
                  t.ok ? 'border-accent bg-accent-dim' : 'border-status-critical/50 bg-status-critical/10',
                )}>
                  {t.ok
                    ? <Check size={9} className="text-accent-bright" aria-hidden />
                    : <X size={9} className="text-danger" aria-hidden />}
                </span>
                <div className="text-xs font-semibold">{t.step}</div>
                <p className="mt-0.5 text-xs leading-relaxed text-ink-2">{t.detail}</p>
              </li>
            ))}
          </ol>

          <div className="mt-4 border-t border-border-subtle pt-3.5">
            {notice ? (
              <div className="rounded-md border border-info/30 bg-info/10 px-3 py-2.5 text-sm text-info">
                {notice}
              </div>
            ) : rollbackAsk ? (
              <div className="rounded-md border border-status-warning/30 bg-status-warning/5 p-3.5">
                <p className="text-sm">
                  Undo <span className="font-mono font-semibold">{selected.type}</span> on{' '}
                  <span className="font-mono">{selected.target}</span>? The undo is recorded as its own
                  provenance step — history is never rewritten.
                </p>
                <div className="mt-2.5 flex gap-2">
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={busy}
                    onClick={() => run(() => endpoints.rollback(selected.id), 'Rolled back — the undo is now its own provenance record.')}
                  >
                    {busy && <Loader2 size={13} className="animate-spin" aria-hidden />}
                    Confirm rollback
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setRollbackAsk(false)}>Cancel</Button>
                </div>
              </div>
            ) : selected.status === 'proposed' ? (
              // L4 proposals need a human decision — this is the governed
              // autonomy story the whole product is built around.
              <div className="rounded-md border border-status-warning/30 bg-status-warning/5 p-3.5">
                <p className="text-sm">
                  <span className="font-mono font-semibold">{selected.level}</span> — this action is too
                  high-blast-radius to fire on its own. It is waiting for you.
                </p>
                <div className="mt-2.5 flex gap-2">
                  <Button
                    size="sm"
                    disabled={busy}
                    onClick={() => run(() => endpoints.decide(selected.id, 'approve'), 'Approved — action executed and logged.')}
                  >
                    {busy && <Loader2 size={13} className="animate-spin" aria-hidden />}
                    <Check size={13} aria-hidden /> Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => run(() => endpoints.decide(selected.id, 'reject'), 'Rejected — recorded as a training signal.')}
                  >
                    <X size={13} aria-hidden /> Reject
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRollbackAsk(true)}
                disabled={selected.status !== 'executed'}
              >
                <Undo2 size={13} aria-hidden /> One-click rollback
              </Button>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
