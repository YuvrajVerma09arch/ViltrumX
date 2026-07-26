import { useEffect, useState } from 'react'
import { ShieldQuestion, Crown, Save, Loader2 } from 'lucide-react'
import { PageHeader, Card, Segmented, AutonomyBadge, Badge, Button, DataSource } from '../components/ui'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'
import { AUTONOMY_LABELS, type AutonomyLevel } from '../lib/utils'
import { cn } from '../lib/utils'

/** Wire shape of a policy row as the API serves it. */
type PolicyRow = {
  actionType: string
  level: AutonomyLevel
  crownJewelOverride: AutonomyLevel
}

type Policy = {
  action: string
  desc: string
  blast: 'low' | 'medium' | 'high'
  level: AutonomyLevel
  crownOverride: AutonomyLevel
}

const INITIAL: Policy[] = [
  { action: 'open_incident', desc: 'Create + correlate an incident record', blast: 'low', level: 'L1', crownOverride: 'L1' },
  { action: 'generate_compliance_evidence', desc: 'Draft DPDP/CERT-In evidence & reports', blast: 'low', level: 'L1', crownOverride: 'L1' },
  { action: 'revoke_session', desc: 'Invalidate one live session token', blast: 'low', level: 'L2', crownOverride: 'L2' },
  { action: 'force_mfa', desc: 'Require re-auth + MFA on next access', blast: 'low', level: 'L2', crownOverride: 'L2' },
  { action: 'rotate_key', desc: 'Rotate an API key, keep escrow 24h', blast: 'medium', level: 'L2', crownOverride: 'L4' },
  { action: 'block_ip', desc: 'Block source IP with auto-expiry timer', blast: 'medium', level: 'L3', crownOverride: 'L3' },
  { action: 'quarantine_device', desc: 'Isolate a device from SaaS sessions', blast: 'medium', level: 'L3', crownOverride: 'L4' },
  { action: 'disable_identity', desc: 'Freeze an account and all its sessions', blast: 'high', level: 'L4', crownOverride: 'L4' },
]

const LEVEL_OPTIONS = (['L1', 'L2', 'L3', 'L4'] as AutonomyLevel[]).map((l) => ({ value: l, label: l }))

const LADDER: { level: AutonomyLevel; desc: string; reversibility: string }[] = [
  { level: 'L1', desc: 'Enrichment, correlation, evidence gathering, report drafting.', reversibility: 'Read-only' },
  { level: 'L2', desc: 'Low-blast-radius containment, executes then notifies you.', reversibility: 'Trivially reversible' },
  { level: 'L3', desc: 'Medium containment on a timer — reverts itself unless renewed.', reversibility: 'Self-reverting' },
  { level: 'L4', desc: 'High blast radius. The system proposes; a human approves.', reversibility: 'Human-gated' },
]

const DESCRIPTIONS = Object.fromEntries(INITIAL.map((p) => [p.action, p]))

export default function AutonomyConsole() {
  const remote = useApi<PolicyRow[]>(() => endpoints.policies(), [])
  const [policies, setPolicies] = useState(INITIAL)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')

  // Merge the server's dial with our local copy for the human-readable
  // description and blast-radius column, which the API doesn't carry.
  useEffect(() => {
    if (!remote.data.length) return
    setPolicies(
      remote.data.map((row) => ({
        action: row.actionType,
        desc: DESCRIPTIONS[row.actionType]?.desc ?? '',
        blast: DESCRIPTIONS[row.actionType]?.blast ?? 'medium',
        level: row.level,
        crownOverride: row.crownJewelOverride,
      })),
    )
    setDirty(false)
  }, [remote.data])

  function set(i: number, key: 'level' | 'crownOverride', v: AutonomyLevel) {
    setPolicies(policies.map((p, idx) => (idx === i ? { ...p, [key]: v } : p)))
    setDirty(true)
    setNotice('')
  }

  // Saving writes a NEW immutable policy version — the dial is an auditable
  // object, so past decisions always resolve against the version in force.
  async function save() {
    setSaving(true)
    try {
      await endpoints.savePolicies(
        policies.map((p) => ({
          actionType: p.action,
          level: p.level,
          crownJewelOverride: p.crownOverride,
        })),
      )
      setNotice('Saved — a new policy version is now in force.')
      setDirty(false)
      remote.reload()
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'Could not save the dial.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Autonomy Console"
        subtitle="The governed-autonomy dial — per action type, per criticality. The policy itself is an object in the ontology, versioned and auditable."
      >
        <div className="flex items-center gap-2">
          <DataSource live={remote.live} loading={remote.loading} />
          <Badge tone="green">{remote.data.length ? 'POLICY ACTIVE' : 'DEFAULTS'}</Badge>
          <Button size="sm" onClick={save} disabled={!dirty || saving}>
            {saving ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <Save size={13} aria-hidden />}
            {dirty ? 'Save new version' : 'Saved'}
          </Button>
        </div>
      </PageHeader>

      {/* Ladder explainer */}
      <div className="grid gap-3 md:grid-cols-4">
        {LADDER.map((l) => (
          <div key={l.level} className="rounded-lg border border-border bg-surface p-4">
            <AutonomyBadge level={l.level} />
            <p className="mt-2.5 text-sm leading-relaxed text-ink-2">{l.desc}</p>
            <p className="mt-2 font-mono text-[11px] text-ink-3">{l.reversibility}</p>
          </div>
        ))}
      </div>

      {notice && (
        <p className="mt-4 rounded-md border border-info/30 bg-info/10 px-3 py-2.5 text-sm text-info">{notice}</p>
      )}

      {/* Policy matrix */}
      <Card title="Action policy matrix — PayKraft defaults" className="mt-4" padded={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-2.5 text-left font-mono text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Action type</th>
                <th className="px-4 py-2.5 text-left font-mono text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Typical blast radius</th>
                <th className="px-4 py-2.5 text-left font-mono text-[11px] font-semibold tracking-wider text-ink-3 uppercase">Default level</th>
                <th className="px-4 py-2.5 text-left font-mono text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  <span className="inline-flex items-center gap-1"><Crown size={11} className="text-status-warning" aria-hidden /> Crown-jewel override</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {policies.map((p, i) => (
                <tr key={p.action} className="hover:bg-surface-2/50">
                  <td className="px-4 py-3">
                    <div className="font-mono text-[13px] font-semibold">{p.action}</div>
                    <div className="mt-0.5 text-xs text-ink-3">{p.desc}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'font-mono text-xs font-medium uppercase',
                      p.blast === 'low' && 'text-status-good',
                      p.blast === 'medium' && 'text-status-warning',
                      p.blast === 'high' && 'text-danger',
                    )}>
                      {p.blast}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <Segmented ariaLabel={`Default level for ${p.action}`} options={LEVEL_OPTIONS} value={p.level} onChange={(v) => set(i, 'level', v)} />
                      <span className="hidden font-mono text-[11px] text-ink-3 lg:inline">{AUTONOMY_LABELS[p.level]}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Segmented ariaLabel={`Crown-jewel override for ${p.action}`} options={LEVEL_OPTIONS} value={p.crownOverride} onChange={(v) => set(i, 'crownOverride', v)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="mt-4 flex items-start gap-3 rounded-lg border border-border bg-surface p-4">
        <ShieldQuestion size={18} className="mt-0.5 shrink-0 text-info" aria-hidden />
        <p className="text-sm leading-relaxed text-ink-2">
          <span className="font-medium text-ink">Trust is earned, not assumed.</span> New tenants start with
          everything at L1/L4. Each week the nightly purple-team score and your override history propose a
          dial adjustment — you accept or reject it, and that decision is itself recorded in provenance.
          Every founder override becomes a labeled training signal for the Noise-Gate and Detection models.
        </p>
      </div>
    </div>
  )
}
