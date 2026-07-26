import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert, BellOff, Zap, Target, ArrowRight } from 'lucide-react'
import { PageHeader, Card, StatTile, SeverityBadge, StatusPill, Badge, DataSource } from '../components/ui'
import { AGENTS, INCIDENTS, ACTIVITY_FEED, type Agent, type Incident, type Action } from '../data/mock'
import { endpoints } from '../lib/api'
import { useApi, useLiveFeed, type FeedLine } from '../lib/hooks'
import { cn } from '../lib/utils'

export default function CommandDeck() {
  const agents = useApi<Agent[]>(() => endpoints.agents(), AGENTS)
  const incidents = useApi<Incident[]>(() => endpoints.incidents(), INCIDENTS)
  const actions = useApi<Action[]>(() => endpoints.actions(), [])
  const seed = useApi<FeedLine[]>(() => endpoints.feed(), ACTIVITY_FEED as FeedLine[])
  const { lines, connected } = useLiveFeed(seed.data)

  // Stat tiles are derived from the same data the tables show, so they can
  // never drift from it the way hardcoded numbers did.
  const stats = useMemo(() => {
    const open = incidents.data.filter((i) => i.status !== 'resolved')
    const critical = open.filter((i) => i.severity === 'critical').length
    const pending = actions.data.filter((a) => a.status === 'proposed')
    const fired = actions.data.filter((a) => a.status === 'executed').length
    return {
      open: open.length,
      openHint: `${critical} critical · ${open.length - critical} other`,
      pending: pending.length,
      fired,
      firedHint: `all reversible · ${pending.length} proposal${pending.length === 1 ? '' : 's'} pending`,
    }
  }, [incidents.data, actions.data])

  return (
    <div>
      <PageHeader
        title="Command Deck"
        subtitle="Live view of every agent, incident, and governed action across PayKraft's world."
      >
        <div className="flex items-center gap-2">
          <DataSource live={incidents.live} loading={incidents.loading} />
          {connected && <Badge tone="green">STREAM CONNECTED</Badge>}
          {stats.pending > 0 && (
            <Badge tone="red">
              <ShieldAlert size={11} aria-hidden /> {stats.pending} L4 DECISION
              {stats.pending === 1 ? '' : 'S'} AWAITING YOU
            </Badge>
          )}
        </div>
      </PageHeader>

      {/* Stat row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Open incidents" value={String(stats.open)} hint={stats.openHint} tone="critical" icon={ShieldAlert} />
        <StatTile label="Alerts suppressed (24h)" value="303 / 312" hint="97.1% noise-gated before human eyes" tone="good" icon={BellOff} />
        <StatTile label="Actions fired (24h)" value={String(stats.fired)} hint={stats.firedHint} tone="accent" icon={Zap} />
        <StatTile label="Defense readiness" value="94%" hint="validated last night by purple team" tone="good" icon={Target} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-5">
        {/* Agent pipeline */}
        <Card title="Agent pipeline" className="xl:col-span-3" padded={false}>
          <ul className="grid gap-px bg-border-subtle sm:grid-cols-2">
            {agents.data.map((a) => (
              <li key={a.id} className="bg-surface p-4">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-semibold">{a.name}</span>
                  <span className={cn(
                    'inline-flex items-center gap-1.5 font-mono text-[10px] tracking-wider uppercase',
                    a.status === 'active' && 'text-status-good',
                    a.status === 'idle' && 'text-ink-3',
                    a.status === 'awaiting approval' && 'text-status-warning',
                  )}>
                    <span className={cn(
                      'h-1.5 w-1.5 rounded-full',
                      a.status === 'active' && 'pulse-dot bg-status-good',
                      a.status === 'idle' && 'bg-ink-3',
                      a.status === 'awaiting approval' && 'pulse-dot bg-status-warning',
                    )} aria-hidden />
                    {a.status}
                  </span>
                </div>
                <div className="mt-0.5 text-xs text-ink-3">{a.role}</div>
                <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-ink-2">{a.currentTask}</p>
                <div className="font-data mt-2 text-[11px] text-accent">{a.stat}</div>
              </li>
            ))}
          </ul>
        </Card>

        {/* Incident feed */}
        <Card
          title="Incident feed"
          className="xl:col-span-2"
          padded={false}
          action={<Link to="/app/investigation" className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent-bright">open workspace <ArrowRight size={12} aria-hidden /></Link>}
        >
          <ul className="divide-y divide-border-subtle">
            {incidents.data.map((inc) => (
              <li key={inc.id}>
                <Link to={`/app/investigation?incident=${inc.id}`} className="block px-4 py-3 transition-colors hover:bg-surface-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-ink-2">{inc.id}</span>
                    <div className="flex items-center gap-1.5">
                      <SeverityBadge severity={inc.severity} />
                      <StatusPill status={inc.status} />
                    </div>
                  </div>
                  <p className="mt-1.5 line-clamp-2 text-sm leading-snug">{inc.title}</p>
                  <div className="mt-1.5 flex items-center justify-between font-mono text-[11px] text-ink-3">
                    <span>{inc.entity}</span><span>{inc.time}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Activity stream */}
      <Card
        title="Live decision stream"
        className="mt-4"
        padded={false}
        action={<DataSource live={seed.live} loading={seed.loading} />}
      >
        <div className="max-h-72 space-y-1 overflow-y-auto p-4 font-mono text-xs md:text-[13px]">
          {lines.map((l, i) => (
            <div key={`${l.t}-${i}`} className="feed-in flex gap-3" style={{ animationDelay: `${Math.min(i, 12) * 60}ms` }}>
              <span className="shrink-0 text-ink-3">{l.t}</span>
              <span className={cn(
                'shrink-0 w-24',
                l.tone === 'action' && 'text-accent',
                l.tone === 'warn' && 'text-status-warning',
                l.tone === 'ok' && 'text-status-good',
                l.tone === 'info' && 'text-info',
              )}>
                [{l.agent}]
              </span>
              <span className="text-ink-2">{l.line}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
