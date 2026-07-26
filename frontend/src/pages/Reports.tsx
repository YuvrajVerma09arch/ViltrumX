import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileDown, FileCheck2, Timer, Loader2 } from 'lucide-react'
import { PageHeader, Card, Badge, Button, Table, Td, DataSource } from '../components/ui'
import { FRAMEWORKS, RECENT_EXPORTS } from '../data/mock'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'

export default function Reports() {
  const [exporting, setExporting] = useState<string | null>(null)
  const [exported, setExported] = useState<string[]>([])

  const frameworks = useApi<typeof FRAMEWORKS>(() => endpoints.frameworks(), FRAMEWORKS)
  const recent = useApi<typeof RECENT_EXPORTS>(() => endpoints.exports(), RECENT_EXPORTS)

  // Generates the evidence pack server-side from the provenance trace, then
  // refreshes the recent-exports list so the new pack appears.
  async function doExport(id: string) {
    setExporting(id)
    try {
      await endpoints.exportFramework(id)
      setExported((x) => [...x, id])
      recent.reload()
    } finally {
      setExporting(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="Report & Compliance Center"
        subtitle="Evidence packs generated natively from provenance — not screenshots collected the week before an audit."
      >
        <div className="flex items-center gap-2">
          <DataSource live={frameworks.live} loading={frameworks.loading} />
          <Badge tone="amber"><Timer size={11} aria-hidden /> CERT-IN CLOCK: 5H 27M LEFT ON INC-042</Badge>
        </div>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-2">
        {frameworks.data.map((f) => (
          <Card key={f.id} title={f.name} action={<Badge tone="neutral">{f.region.toUpperCase()}</Badge>}>
            <div className="flex items-center gap-2">
              <FileCheck2 size={15} className="text-accent" aria-hidden />
              <span className="text-sm font-semibold">{f.status}</span>
              <span className="font-mono text-xs text-ink-3">· {f.controls}</span>
            </div>
            <p className="mt-2.5 text-sm leading-relaxed text-ink-2">{f.note}</p>
            <div className="mt-4 flex items-center gap-2">
              <Button size="sm" onClick={() => doExport(f.id)} disabled={exporting !== null || exported.includes(f.id)}>
                {exporting === f.id
                  ? <><Loader2 size={13} className="animate-spin" aria-hidden /> generating…</>
                  : exported.includes(f.id)
                    ? 'Exported ✓'
                    : <><FileDown size={13} aria-hidden /> Export evidence pack (PDF)</>}
              </Button>
              {f.id === 'certin' && (
                <Link to="/app/investigation">
                  <Button size="sm" variant="outline">Preview bilingual narrative</Button>
                </Link>
              )}
            </div>
            {exported.includes(f.id) && (
              <p className="mt-2.5 rounded-md border border-accent/25 bg-accent-dim/40 px-3 py-2 font-mono text-[11px] text-accent-bright">
                {f.name.split(' ')[0].toLowerCase()}-evidence-2026-07-09.pdf · signed manifest · stored in audit vault
              </p>
            )}
          </Card>
        ))}
      </div>

      <Card title="Recent exports" className="mt-4" padded={false}>
        <Table head={['Document', 'Format', 'Generated']}>
          {recent.data.map((r) => (
            <tr key={r.name} className="hover:bg-surface-2/50">
              <Td className="font-medium">{r.name}</Td>
              <Td className="font-mono text-xs text-ink-2">{r.kind}</Td>
              <Td className="font-mono text-xs text-ink-3">{r.when}</Td>
            </tr>
          ))}
        </Table>
      </Card>

      <div className="mt-4 rounded-lg border border-border bg-surface p-4">
        <p className="text-sm leading-relaxed text-ink-2">
          <span className="font-medium text-ink">How the CERT-In draft works:</span> the moment an incident is
          confirmed, the Explainability agent assembles the six mandated fields from provenance (nature of
          incident, affected systems, timeline, actions taken, point of contact, indicators) into the CERT-In
          format — in English and Hindi — and starts the 6-hour countdown visibly. You review and file; the
          system never files on its own.
        </p>
      </div>
    </div>
  )
}
