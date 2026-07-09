import { useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, MiniMap, Handle, Position, type Node, type Edge, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { User, Bot, KeyRound, Laptop, Cloud, GitBranch, Grid2x2, Database, X } from 'lucide-react'
import { PageHeader, Card, Badge, CriticalityBadge } from '../components/ui'
import { ONT_NODES, ONT_EDGES, type OntNode, type OntNodeType } from '../data/mock'
import { cn } from '../lib/utils'

/** Entity-class colors (validated categorical slots — identity also carried by icon + label). */
const TYPE_META: Record<OntNodeType, { color: string; icon: typeof User; cls: string }> = {
  user: { color: '#3987e5', icon: User, cls: 'Identity' },
  service: { color: '#3987e5', icon: Bot, cls: 'Identity' },
  apikey: { color: '#3987e5', icon: KeyRound, cls: 'Identity' },
  device: { color: '#199e70', icon: Laptop, cls: 'Device' },
  cloud: { color: '#c98500', icon: Cloud, cls: 'Cloud' },
  repo: { color: '#9085e9', icon: GitBranch, cls: 'Repo' },
  saas: { color: '#d55181', icon: Grid2x2, cls: 'SaaS' },
  data: { color: '#d95926', icon: Database, cls: 'Data asset' },
}

type FlowNode = Node<{ ont: OntNode }, 'entity'>

function EntityNode({ data, selected }: NodeProps<FlowNode>) {
  const { ont } = data
  const meta = TYPE_META[ont.type]
  const Icon = meta.icon
  return (
    <div
      className={cn(
        'rounded-md border bg-surface px-3 py-2 shadow-md transition-colors',
        ont.compromised ? 'border-status-critical' : 'border-border',
        selected && 'ring-2 ring-accent',
      )}
      style={{ borderLeftWidth: 3, borderLeftColor: meta.color }}
    >
      <Handle type="target" position={Position.Left} className="!bg-ink-3" />
      <div className="flex items-center gap-2">
        <Icon size={13} style={{ color: meta.color }} aria-hidden />
        <span className="font-mono text-xs font-semibold text-ink">{ont.label}</span>
        {ont.criticality === 'crown-jewel' && <span className="font-mono text-[9px] font-bold text-status-warning">◆</span>}
      </div>
      {ont.compromised && (
        <div className="mt-1 font-mono text-[9px] font-semibold tracking-wider text-danger uppercase">on attack path</div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-ink-3" />
    </div>
  )
}

const nodeTypes = { entity: EntityNode }

export default function OntologyExplorer() {
  const [selected, setSelected] = useState<OntNode | null>(null)
  const [attackOnly, setAttackOnly] = useState(false)

  const nodes: FlowNode[] = useMemo(
    () => ONT_NODES
      .filter((n) => !attackOnly || n.compromised || ONT_EDGES.some((e) => e.attack && (e.source === n.id || e.target === n.id)))
      .map((n) => ({ id: n.id, type: 'entity', position: { x: n.x, y: n.y }, data: { ont: n } })),
    [attackOnly],
  )

  const edges: Edge[] = useMemo(
    () => ONT_EDGES
      .filter((e) => !attackOnly || e.attack)
      .map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        animated: !!e.attack,
        style: { stroke: e.attack ? 'var(--color-status-critical)' : 'var(--color-axis)', strokeWidth: e.attack ? 2 : 1.25 },
        labelStyle: { fill: e.attack ? '#e66767' : '#6e7b8a', fontFamily: 'JetBrains Mono', fontSize: 9 },
        labelBgStyle: { fill: '#0d1117', fillOpacity: 0.85 },
      })),
    [attackOnly],
  )

  return (
    <div>
      <PageHeader
        title="Ontology Explorer"
        subtitle="PayKraft's world as a typed graph — 16 objects, 15 links, synced from Workspace, GitHub, and CloudTrail 41 seconds ago."
      >
        <button
          onClick={() => setAttackOnly(!attackOnly)}
          className={cn(
            'cursor-pointer rounded-md border px-3 py-1.5 font-mono text-xs font-medium transition-colors',
            attackOnly ? 'border-status-critical/50 bg-status-critical/10 text-danger' : 'border-border text-ink-2 hover:text-ink',
          )}
        >
          {attackOnly ? 'Showing INC-042 attack path' : 'Isolate attack path'}
        </button>
      </PageHeader>

      <div className="relative h-[calc(100dvh-230px)] min-h-[480px] overflow-hidden rounded-lg border border-border bg-surface">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
          onNodeClick={(_, node) => setSelected((node as FlowNode).data.ont)}
          onPaneClick={() => setSelected(null)}
          colorMode="dark"
        >
          <Background gap={24} size={1} color="#21262d" />
          <Controls position="bottom-left" />
          <MiniMap pannable zoomable className="!bg-bg" nodeColor={(n) => TYPE_META[(n as FlowNode).data.ont.type].color} />
        </ReactFlow>

        {/* Legend */}
        <div className="absolute top-3 left-3 rounded-md border border-border bg-bg/90 p-3 backdrop-blur">
          <div className="mb-2 font-mono text-[10px] font-semibold tracking-widest text-ink-3 uppercase">Object types</div>
          <ul className="space-y-1.5">
            {[
              ['Identity', '#3987e5'], ['Device', '#199e70'], ['Cloud', '#c98500'],
              ['Repo', '#9085e9'], ['SaaS', '#d55181'], ['Data asset', '#d95926'],
            ].map(([label, color]) => (
              <li key={label} className="flex items-center gap-2 text-xs text-ink-2">
                <span className="h-2 w-2 rounded-sm" style={{ background: color }} aria-hidden /> {label}
              </li>
            ))}
            <li className="flex items-center gap-2 pt-1 text-xs text-ink-2">
              <span className="font-mono text-[10px] font-bold text-status-warning">◆</span> crown jewel
            </li>
            <li className="flex items-center gap-2 text-xs text-ink-2">
              <span className="h-0.5 w-4 bg-status-critical" aria-hidden /> attack link (live)
            </li>
          </ul>
        </div>

        {/* Detail panel */}
        {selected && (
          <aside className="absolute top-3 right-3 bottom-3 w-72 overflow-y-auto rounded-md border border-border bg-bg/95 p-4 backdrop-blur">
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-mono text-sm font-bold break-all">{selected.label}</h2>
              <button aria-label="Close details" onClick={() => setSelected(null)} className="cursor-pointer rounded p-1 text-ink-3 hover:bg-surface-2 hover:text-ink">
                <X size={14} aria-hidden />
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone="blue">{TYPE_META[selected.type].cls.toUpperCase()}</Badge>
              <CriticalityBadge criticality={selected.criticality} />
              {selected.compromised && <Badge tone="red">ON ATTACK PATH</Badge>}
            </div>
            <p className="mt-3 text-sm leading-relaxed text-ink-2">{selected.meta}</p>
            <div className="mt-4 border-t border-border-subtle pt-3">
              <div className="font-mono text-[10px] font-semibold tracking-widest text-ink-3 uppercase">Links</div>
              <ul className="mt-2 space-y-1.5 font-mono text-xs text-ink-2">
                {ONT_EDGES.filter((e) => e.source === selected.id || e.target === selected.id).map((e) => {
                  const otherId = e.source === selected.id ? e.target : e.source
                  const other = ONT_NODES.find((n) => n.id === otherId)
                  return (
                    <li key={e.id} className={cn(e.attack && 'text-danger')}>
                      {e.source === selected.id ? '→' : '←'} {e.label} · {other?.label}
                    </li>
                  )
                })}
              </ul>
            </div>
            <p className="mt-4 rounded-md border border-border-subtle bg-surface px-3 py-2 text-xs leading-relaxed text-ink-3">
              Blast radius, lateral-movement paths, and criticality weighting are computed over these
              links in Neo4j (GDS shortest-path / PageRank).
            </p>
          </aside>
        )}
      </div>

      <Card title="Why this graph is the moat" className="mt-4">
        <p className="text-sm leading-relaxed text-ink-2">
          Every alert, action, and report is grounded in this ontology — the same three primitives
          (Objects, Links, Actions) Palantir uses in Foundry. When the Detection agent flags
          <span className="font-mono text-ink"> priya.sharma</span>, the graph already knows she can reach
          <span className="font-mono text-ink"> s3://customers-db-backups</span> through a PAT and a leaked key —
          so the response targets the path, not just the alert.
        </p>
      </Card>
    </div>
  )
}
