import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { PageHeader, Card, StatTile, Toggle, ProgressBar, Badge, DataSource } from '../components/ui'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'

// Shapes served by the risk endpoints. Declared locally so this page has no
// dependency on the demo fixtures in `data/mock.ts`.
type RiskPoint = { day: string; org: number | null; forecast: number | null }
type EntityRisk = { entity: string; type: string; score: number; trend: string; reason: string }
type ReadinessPoint = { week: string; score: number }

const AXIS_TICK = { fill: '#6e7b8a', fontSize: 11, fontFamily: 'JetBrains Mono' }
const TOOLTIP_STYLE = {
  background: '#0d1117', border: '1px solid #30363d', borderRadius: 8,
  fontFamily: 'JetBrains Mono', fontSize: 12, color: '#e6edf3',
}

function ReadinessGauge({ value }: { value: number }) {
  const r = 56
  const circ = Math.PI * r // semicircle
  const filled = (value / 100) * circ
  return (
    <svg viewBox="0 0 140 84" className="mx-auto w-44" role="img" aria-label={`Defense readiness ${value} percent`}>
      <path d={`M 14 76 A ${r} ${r} 0 0 1 126 76`} fill="none" stroke="#21262d" strokeWidth="10" strokeLinecap="round" />
      <path
        d={`M 14 76 A ${r} ${r} 0 0 1 126 76`} fill="none" stroke="var(--color-accent)" strokeWidth="10" strokeLinecap="round"
        strokeDasharray={`${filled} ${circ}`}
      />
      <text x="70" y="66" textAnchor="middle" fontFamily="JetBrains Mono" fontWeight="700" fontSize="26" fill="#e6edf3">{value}%</text>
    </svg>
  )
}

export default function RiskDashboard() {
  const [founderMode, setFounderMode] = useState(false)

  // Empty defaults: a failed request or an empty tenant must render honest
  // empty states, never the PayKraft demo fixtures.
  const trend = useApi<RiskPoint[]>(() => endpoints.riskTrend(), [])
  const entities = useApi<EntityRisk[]>(() => endpoints.riskEntities(), [])
  const readiness = useApi<ReadinessPoint[]>(() => endpoints.readiness(), [])

  // Stat tiles derive from the same data the charts show, so they can never
  // drift from it the way hardcoded demo numbers did.
  const lastObserved = [...trend.data].reverse().find((p) => p.org !== null)?.org
  const lastForecast = [...trend.data].reverse().find((p) => p.forecast !== null)?.forecast
  const lastReadiness = readiness.data[readiness.data.length - 1]
  const aboveThreshold = entities.data.filter((e) => e.score > 70).length

  return (
    <div>
      <PageHeader
        title="Risk & Prediction"
        subtitle={founderMode
          ? 'The same numbers your security system sees — translated into what they cost.'
          : 'Behavioral ML risk scores, 5-day forecast, and defense readiness — recomputed hourly.'}
      >
        <DataSource live={trend.live} loading={trend.loading} />
        <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5">
          <span className="text-xs font-medium">Founder Mode</span>
          <Toggle checked={founderMode} onChange={setFounderMode} label="Founder Mode" />
        </div>
      </PageHeader>

      {/* Stat row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {founderMode ? (
          <>
            <StatTile label="Value protected today" value="—" hint="no exposure data yet" tone="good" />
            <StatTile label="Max DPDP penalty exposure" value="—" hint="no statutory exposure figure available" tone="warning" />
            <StatTile label="Your security spend" value="—" hint="no billing data in this view" tone="accent" />
            <StatTile label="Decisions waiting on you" value="—" hint="open Provenance to review decisions" tone="critical" />
          </>
        ) : (
          <>
            <StatTile label="Org risk score" value={lastObserved != null ? `${lastObserved} / 100` : '—'} hint={lastObserved != null ? 'latest observed score' : 'no risk data yet'} tone="critical" icon={TrendingUp} />
            <StatTile label="5-day forecast" value={lastForecast ?? '—'} hint={lastForecast != null ? 'ML forecast from behavioral features' : 'no forecast data yet'} tone="good" icon={TrendingDown} />
            <StatTile label="Entities above threshold" value={String(aboveThreshold)} hint={entities.data.length ? `of ${entities.data.length} tracked entities` : 'no entities tracked yet'} tone="warning" />
            <StatTile label="Defense readiness" value={lastReadiness ? `${lastReadiness.score}%` : '—'} hint={lastReadiness ? 'nightly purple-team validated' : 'no readiness data yet'} tone="good" />
          </>
        )}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {/* Risk trend + forecast */}
        <Card title={founderMode ? 'How exposed were we? (last 14 days)' : 'Org risk — observed & forecast'} className="xl:col-span-2">
          {trend.data.length === 0 ? (
            <div className="flex h-[260px] items-center justify-center font-mono text-xs text-ink-3">
              No risk data yet.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trend.data} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="#21262d" vertical={false} />
                <XAxis dataKey="day" tick={AXIS_TICK} axisLine={{ stroke: '#383f47' }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: '#383f47' }} />
                <Legend wrapperStyle={{ fontFamily: 'JetBrains Mono', fontSize: 12, color: '#9ba7b4' }} />
                <Line name="observed risk" type="monotone" dataKey="org" stroke="#3987e5" strokeWidth={2} dot={{ r: 3, fill: '#3987e5', stroke: '#161b22', strokeWidth: 2 }} connectNulls={false} />
                <Line name="ML forecast" type="monotone" dataKey="forecast" stroke="#3987e5" strokeWidth={2} strokeDasharray="6 5" dot={false} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
          <p className="mt-2 text-xs text-ink-3">
            {trend.data.length === 0
              ? 'No forecast available yet.'
              : founderMode
                ? 'The dotted line is the system\'s prediction — how exposure is expected to trend as containment holds.'
                : 'Forecast: gradient-boosted model over behavioral features + graph centrality.'}
          </p>
        </Card>

        {/* Readiness */}
        <Card title="Defense Readiness Score">
          {readiness.data.length === 0 ? (
            <div className="flex h-[180px] items-center justify-center font-mono text-xs text-ink-3">
              No readiness data yet.
            </div>
          ) : (
            <>
              <ReadinessGauge value={lastReadiness?.score ?? 0} />
              <p className="mt-1 text-center text-xs text-ink-3">computed live from the nightly purple-team sweep</p>
              <ResponsiveContainer width="100%" height={110}>
                <LineChart data={readiness.data} margin={{ top: 16, right: 8, bottom: 0, left: -22 }}>
                  <XAxis dataKey="week" tick={AXIS_TICK} axisLine={{ stroke: '#383f47' }} tickLine={false} />
                  <YAxis domain={[60, 100]} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: '#383f47' }} />
                  <Line name="readiness" type="monotone" dataKey="score" stroke="#199e70" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}
        </Card>
      </div>

      {/* Entity risk table */}
      <Card title={founderMode ? 'What should worry you, in plain words' : 'Highest-risk entities'} className="mt-4" padded={false}>
        <ul className="divide-y divide-border-subtle">
          {entities.data.length === 0 && (
            <li className="px-4 py-10 text-center font-mono text-xs text-ink-3">No entities tracked yet.</li>
          )}
          {entities.data.map((e) => (
            <li key={e.entity} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
              <div className="w-56 min-w-0">
                <div className="truncate font-mono text-[13px] font-semibold">{e.entity}</div>
                <Badge tone="neutral" className="mt-1">{e.type.toUpperCase()}</Badge>
              </div>
              <div className="min-w-40 flex-1">
                <ProgressBar value={e.score} tone={e.score > 70 ? 'critical' : e.score > 45 ? 'warning' : 'info'} />
              </div>
              <div className="font-data w-20 text-right text-sm font-bold">
                {e.score}
                <span className={`ml-1.5 text-xs ${e.trend.startsWith('+') ? 'text-danger' : 'text-status-good'}`}>{e.trend}</span>
              </div>
              <p className="w-full text-xs text-ink-3 lg:w-72">{e.reason}</p>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
