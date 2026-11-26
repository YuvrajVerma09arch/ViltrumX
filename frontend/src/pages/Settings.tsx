import { useState } from 'react'
import { UserPlus } from 'lucide-react'
import { PageHeader, Card, Table, Td, Badge, Button, Segmented, Toggle } from '../components/ui'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'
import { cn } from '../lib/utils'

// Shapes served by /members and /billing/invoices. Declared locally so this
// page has no dependency on the demo fixtures in `data/mock.ts`.
type Member = { name: string; email: string; role: string; last: string }
type Invoice = { id: string; period: string; amount: string; gst: string; status: string }
type PlanInfo = { id: string; name: string; amount_inr: number }

type Tab = 'team' | 'tenant' | 'billing'

const ROLE_TONE: Record<string, 'green' | 'blue' | 'purple' | 'neutral'> = {
  Owner: 'green', Admin: 'blue', Analyst: 'purple', Viewer: 'neutral',
}

// Indicative plan copy — actual amounts come from /billing/plans (server truth).
const PLAN_PITCH: Record<string, string> = {
  seed: 'Up to 25 identities · 2 connectors · L1–L2 autonomy',
  growth: 'Up to 150 identities · all connectors · full L1–L4 ladder · purple team nightly',
  scale: '300+ identities · self-hosted inference · RBI pack · dedicated support',
}

/** Load Razorpay Checkout.js once and run a payment for a plan. */
async function startCheckout(plan: PlanInfo) {
  const order = (await endpoints.createOrder(plan.id)) as {
    order_id: string; amount: number; currency: string; key_id: string
  }
  await new Promise<void>((resolve, reject) => {
    const w = window as unknown as { Razorpay?: new (o: unknown) => { open: () => void } }
    const launch = () => {
      if (!w.Razorpay) return reject(new Error('Razorpay Checkout failed to load'))
      const rzp = new w.Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'ViltrumX',
        order_id: order.order_id,
        theme: { color: '#6366f1' },
        handler: async (resp: {
          razorpay_order_id: string
          razorpay_payment_id: string
          razorpay_signature: string
        }) => {
          await endpoints.verifyPayment(resp)
          resolve()
        },
        modal: { ondismiss: () => resolve() },
      })
      rzp.open()
    }
    if (w.Razorpay) return launch()
    const s = document.createElement('script')
    s.src = 'https://checkout.razorpay.com/v1/checkout.js'
    s.onload = launch
    s.onerror = () => reject(new Error('Could not load Razorpay Checkout'))
    document.body.appendChild(s)
  })
}

export default function Settings() {
  const members = useApi<Member[]>(() => endpoints.members(), [])
  const invoices = useApi<Invoice[]>(() => endpoints.invoices(), [])
  const billing = useApi<{ configured: boolean; plans: PlanInfo[] }>(
    () => endpoints.billingPlans(),
    { configured: false, plans: [] },
  )

  const [tab, setTab] = useState<Tab>('team')
  const [whatsapp, setWhatsapp] = useState(true)
  const [hindiDigest, setHindiDigest] = useState(true)
  const [paying, setPaying] = useState<string | null>(null)

  async function subscribe(plan: PlanInfo) {
    setPaying(plan.id)
    try {
      await startCheckout(plan)
      invoices.reload()
    } catch (err) {
      console.error('checkout failed', err)
      alert((err as Error).message || 'Could not start checkout.')
    } finally {
      setPaying(null)
    }
  }

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
              {members.data.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-3 py-10 text-center font-mono text-xs text-ink-3">No members yet.</td>
                </tr>
              )}
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
                  <div className="text-xs text-ink-3">Narratives are English-only for now; Hindi/Gujarati are on the roadmap.</div>
                </div>
                <Toggle checked={hindiDigest} onChange={setHindiDigest} label="Hindi digest" />
              </li>
              <li className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">Slack #security-ops</div>
                  <div className="text-xs text-ink-3">L2/L3 action notifications — connector not wired yet</div>
                </div>
                <Badge tone="neutral">NOT CONNECTED</Badge>
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
          <p className="rounded-md border border-status-warning/30 bg-status-warning/5 px-3 py-2.5 text-xs leading-relaxed text-ink-2">
            Indicative pricing — billing is not live yet; contact sales.
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            {billing.data.plans.length === 0 && (
              <p className="col-span-3 font-mono text-xs text-ink-3">Loading plans…</p>
            )}
            {billing.data.plans.map((p) => (
              <div key={p.id} className="rounded-lg border border-border bg-surface p-5">
                <h3 className="font-mono text-sm font-bold">{p.name}</h3>
                <div className="font-data mt-3 text-2xl font-bold">
                  ₹{p.amount_inr.toLocaleString('en-IN')}
                  <span className="text-sm font-normal text-ink-3">/mo + GST</span>
                </div>
                <p className="mt-2.5 text-xs leading-relaxed text-ink-2">{PLAN_PITCH[p.id] ?? ''}</p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-4"
                  disabled={!billing.data.configured || paying !== null}
                  title={billing.data.configured ? 'Pay with Razorpay' : 'Billing not configured on this server'}
                  onClick={() => subscribe(p)}
                >
                  {paying === p.id ? 'Opening…' : 'Subscribe'}
                </Button>
              </div>
            ))}
          </div>
          <Card title="Invoices" padded={false}>
            <Table head={['Invoice', 'Period', 'Amount', 'Tax', 'Status']}>
              {invoices.data.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-10 text-center font-mono text-xs text-ink-3">No invoices yet.</td>
                </tr>
              )}
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
