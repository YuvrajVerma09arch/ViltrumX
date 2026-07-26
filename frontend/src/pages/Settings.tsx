import { useState } from 'react'
import { UserPlus, Check } from 'lucide-react'
import { PageHeader, Card, Table, Td, Badge, Button, Segmented, Toggle } from '../components/ui'
import { MEMBERS, INVOICES } from '../data/mock'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'
import { cn } from '../lib/utils'

type Tab = 'team' | 'tenant' | 'billing'

const ROLE_TONE: Record<string, 'green' | 'blue' | 'purple' | 'neutral'> = {
  Owner: 'green', Admin: 'blue', Analyst: 'purple', Viewer: 'neutral',
}

const PLANS = [
  { name: 'Seed', price: '₹9,999', per: '/mo + GST', pitch: 'Up to 25 identities · 2 connectors · L1–L2 autonomy', current: false },
  { name: 'Growth', price: '₹29,499', per: '/mo + GST', pitch: 'Up to 150 identities · all connectors · full L1–L4 ladder · purple team nightly', current: true },
  { name: 'Scale', price: '₹74,999', per: '/mo + GST', pitch: '300+ identities · self-hosted inference · RBI pack · dedicated support', current: false },
]

export default function Settings() {
  const members = useApi<typeof MEMBERS>(() => endpoints.members(), MEMBERS)
  const invoices = useApi<typeof INVOICES>(() => endpoints.invoices(), INVOICES)

  const [tab, setTab] = useState<Tab>('team')
  const [whatsapp, setWhatsapp] = useState(true)
  const [hindiDigest, setHindiDigest] = useState(true)

  return (
    <div>
      <PageHeader title="Settings & Administration" subtitle="Org roles, tenant defaults, and billing — multi-tenant, RBAC-scoped, audit-logged.">
        <Segmented
          ariaLabel="Settings section"
          value={tab}
          onChange={setTab}
          options={[{ value: 'team', label: 'Team & RBAC' }, { value: 'tenant', label: 'Tenant defaults' }, { value: 'billing', label: 'Billing' }]}
        />
      </PageHeader>

      {tab === 'team' && (
        <div className="grid gap-4 xl:grid-cols-3">
          <Card title="Members" className="xl:col-span-2" padded={false}
            action={
              <Button size="sm" variant="outline" disabled title="Invitations ship with SSO — roadmap, not in this build">
                <UserPlus size={13} aria-hidden /> Invite
              </Button>
            }
          >
            <Table head={['Member', 'Role', 'Last active']}>
              {members.data.map((m) => (
                <tr key={m.email} className="hover:bg-surface-2/50">
                  <Td>
                    <div className="text-sm font-medium">{m.name}</div>
                    <div className="font-mono text-xs text-ink-3">{m.email}</div>
                  </Td>
                  <Td><Badge tone={ROLE_TONE[m.role]}>{m.role.toUpperCase()}</Badge></Td>
                  <Td className={cn('font-mono text-xs', m.last.includes('revoked') ? 'text-danger' : 'text-ink-3')}>{m.last}</Td>
                </tr>
              ))}
            </Table>
          </Card>
          <Card title="Role capabilities">
            <ul className="space-y-3 text-sm text-ink-2">
              <li><Badge tone="green">OWNER</Badge><p className="mt-1 text-xs">Approves L4 actions, edits autonomy policy, billing.</p></li>
              <li><Badge tone="blue">ADMIN</Badge><p className="mt-1 text-xs">Manages connectors, criticality tags, and members.</p></li>
              <li><Badge tone="purple">ANALYST</Badge><p className="mt-1 text-xs">Works investigations, proposes (not approves) actions.</p></li>
              <li><Badge tone="neutral">VIEWER</Badge><p className="mt-1 text-xs">Read-only: dashboards, reports, Founder Mode.</p></li>
            </ul>
          </Card>
        </div>
      )}

      {tab === 'tenant' && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Notifications">
            <ul className="space-y-4">
              <li className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">WhatsApp founder digest</div>
                  <div className="text-xs text-ink-3">Daily 08:00 IST summary + instant L4 proposals</div>
                </div>
                <Toggle checked={whatsapp} onChange={setWhatsapp} label="WhatsApp digest" />
              </li>
              <li className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">Digest language: Hindi</div>
                  <div className="text-xs text-ink-3">Narratives render via IndicTrans2 — English fallback</div>
                </div>
                <Toggle checked={hindiDigest} onChange={setHindiDigest} label="Hindi digest" />
              </li>
              <li className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">Slack #security-ops</div>
                  <div className="text-xs text-ink-3">All L2/L3 action notifications</div>
                </div>
                <Badge tone="green"><Check size={11} aria-hidden /> CONNECTED</Badge>
              </li>
            </ul>
          </Card>
          <Card title="Data & inference">
            <dl className="space-y-3.5 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-ink-2">Data residency</dt>
                <dd className="font-mono text-xs">ap-south-1 (Mumbai)</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-2">Explanation LLM</dt>
                <dd className="font-mono text-xs">cloud API · <span className="text-accent">self-hosted available</span></dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-2">Detection models</dt>
                <dd className="font-mono text-xs">local · deterministic · never LLM</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-2">Audit log retention</dt>
                <dd className="font-mono text-xs">append-only · 7 years</dd>
              </div>
            </dl>
            <p className="mt-4 rounded-md border border-border-subtle bg-bg px-3 py-2.5 text-xs leading-relaxed text-ink-3">
              Sovereign mode runs the explanation layer on a self-hosted open-weight model (vLLM/Ollama)
              so no telemetry leaves your VPC — relevant if your DPDP posture requires it.
            </p>
          </Card>
        </div>
      )}

      {tab === 'billing' && (
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            {PLANS.map((p) => (
              <div key={p.name} className={cn(
                'rounded-lg border p-5',
                p.current ? 'border-accent bg-accent-dim/30' : 'border-border bg-surface',
              )}>
                <div className="flex items-center justify-between">
                  <h3 className="font-mono text-sm font-bold">{p.name}</h3>
                  {p.current && <Badge tone="green">CURRENT</Badge>}
                </div>
                <div className="font-data mt-3 text-2xl font-bold">{p.price}<span className="text-sm font-normal text-ink-3">{p.per}</span></div>
                <p className="mt-2.5 text-xs leading-relaxed text-ink-2">{p.pitch}</p>
                {!p.current && (
                  <Button size="sm" variant="outline" className="mt-4" disabled title="Razorpay checkout is roadmap — billing is fixture-tier in this build">
                    Switch plan
                  </Button>
                )}
              </div>
            ))}
          </div>
          <Card title="Invoices — GST · UPI autopay via Razorpay" padded={false}>
            <Table head={['Invoice', 'Period', 'Amount', 'Tax', 'Status']}>
              {invoices.data.map((inv) => (
                <tr key={inv.id} className="hover:bg-surface-2/50">
                  <Td className="font-mono text-xs">{inv.id}</Td>
                  <Td className="text-sm">{inv.period}</Td>
                  <Td className="font-data text-sm font-semibold">{inv.amount}</Td>
                  <Td className="font-mono text-xs text-ink-3">{inv.gst}</Td>
                  <Td><Badge tone="green">{inv.status.toUpperCase()}</Badge></Td>
                </tr>
              ))}
            </Table>
          </Card>
        </div>
      )}
    </div>
  )
}
