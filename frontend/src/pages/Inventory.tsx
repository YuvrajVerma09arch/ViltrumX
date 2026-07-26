import { useState } from 'react'
import { PageHeader, Card, Table, Td, CriticalityBadge, ProgressBar, Badge, Segmented, DataSource } from '../components/ui'
import { INV_IDENTITIES, INV_CLOUD, INV_REPOS, INV_SAAS } from '../data/mock'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'
import type { Criticality } from '../lib/utils'

type Tab = 'identities' | 'cloud' | 'repos' | 'saas'

type Row = { name: string; kind: string; posture?: string; mfa?: boolean; risk: number; criticality: Criticality }

const TABS: { value: Tab; label: string }[] = [
  { value: 'identities', label: 'Identities' },
  { value: 'cloud', label: 'Cloud' },
  { value: 'repos', label: 'Repos' },
  { value: 'saas', label: 'SaaS' },
]

const FIXTURES: Record<Tab, Row[]> = {
  identities: INV_IDENTITIES,
  cloud: INV_CLOUD,
  repos: INV_REPOS,
  saas: INV_SAAS,
}

export default function Inventory() {
  const [tab, setTab] = useState<Tab>('identities')

  // Refetches on tab change — the category is a server-side query param.
  const inventory = useApi<Row[]>(() => endpoints.inventory(tab), FIXTURES[tab], [tab])
  const rows = inventory.data

  return (
    <div>
      <PageHeader
        title="Attack Surface Inventory"
        subtitle={`Everything the ontology tracks, with posture and founder-assigned criticality. ${rows.length} object${rows.length === 1 ? '' : 's'} in this category.`}
      >
        <DataSource live={inventory.live} loading={inventory.loading} />
        <Segmented ariaLabel="Inventory category" options={TABS} value={tab} onChange={setTab} />
      </PageHeader>

      <Card padded={false}>
        <Table head={[
          'Object', tab === 'identities' ? 'MFA' : 'Posture', 'Risk', 'Criticality',
        ]}>
          {rows.map((r) => (
            <tr key={r.name} className="hover:bg-surface-2/50">
              <Td>
                <div className="font-mono text-[13px] font-semibold">{r.name}</div>
                <div className="mt-0.5 text-xs text-ink-3">{r.kind}</div>
              </Td>
              <Td className="max-w-72">
                {tab === 'identities' ? (
                  r.mfa ? <Badge tone="green">MFA ON</Badge> : <Badge tone="red">NO MFA</Badge>
                ) : (
                  <span className="text-xs text-ink-2">{r.posture}</span>
                )}
              </Td>
              <Td className="w-52">
                <div className="flex items-center gap-3">
                  <div className="w-28"><ProgressBar value={r.risk} tone={r.risk > 70 ? 'critical' : r.risk > 45 ? 'warning' : 'info'} /></div>
                  <span className="font-data text-xs font-semibold">{r.risk}</span>
                </div>
              </Td>
              <Td><CriticalityBadge criticality={r.criticality} /></Td>
            </tr>
          ))}
        </Table>
      </Card>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Card title="Posture summary">
          <ul className="space-y-2 text-sm text-ink-2">
            <li>· 6/6 human identities on MFA — <span className="text-status-good">enforced</span></li>
            <li>· 1 service account without MFA (<span className="font-mono text-xs">ci-deploy-bot</span>) — key-scoped</li>
            <li>· 1 repo with secrets in history — purge scheduled tonight</li>
          </ul>
        </Card>
        <Card title="Crown jewels">
          <ul className="space-y-2 font-mono text-xs text-ink-2">
            <li>◆ s3://customers-db-backups</li>
            <li>◆ rds/payments-db</li>
            <li>◆ Razorpay settlement account</li>
            <li>◆ paykraft-core</li>
          </ul>
          <p className="mt-3 text-xs text-ink-3">Any action touching these requires human approval (L4), regardless of the default dial.</p>
        </Card>
        <Card title="Coverage">
          <ul className="space-y-2 text-sm text-ink-2">
            <li>· Google Workspace — <span className="text-status-good">streaming</span></li>
            <li>· GitHub audit log — <span className="text-status-good">streaming</span></li>
            <li>· AWS CloudTrail — <span className="text-status-good">streaming</span></li>
            <li>· Razorpay — <span className="text-ink-3">not connected</span></li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
