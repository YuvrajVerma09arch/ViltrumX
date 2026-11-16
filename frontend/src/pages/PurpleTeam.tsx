import { useState } from 'react'
import { Swords, Play, Loader2, CalendarClock } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { PageHeader, Card, StatusPill, Button, StatTile, DataSource } from '../components/ui'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'

const AXIS_TICK = { fill: '#6e7b8a', fontSize: 11, fontFamily: 'JetBrains Mono' }
const TOOLTIP_STYLE = {
  background: '#0d1117', border: '1px solid #30363d', borderRadius: 8,
  fontFamily: 'JetBrains Mono', fontSize: 12, color: '#e6edf3',
}

// Shapes served by /purple/scenarios and /purple/scenarios/:id/run. Declared
// locally instead of deriving from the demo fixture in `data/mock.ts`, so a
// real tenant never inherits the demo organization's scenario data.
type Scenario = {
  id: string
  name: string
  desc: string
  lastRun: string
  result: string
  detection: string
  containment: string
}
type ReadinessPoint = { week: string; score: number }

// "41 s" / "6 m 02 s" / "—" → seconds (or null when not run yet).
function toSeconds(s: string): number | null {
  if (!s || s === '—') return null
  const m = s.match(/(?:(\d+)\s*m\s*)?(\d+)\s*s/)
  if (!m) return null
  return (m[1] ? parseInt(m[1], 10) * 60 : 0) + parseInt(m[2], 10)
}
function fmtMedian(values: number[]): string {
  if (!values.length) return '—'
  const sorted = [...values].sort((a, b) => a - b)
  const mid = sorted[Math.floor(sorted.length / 2)]
  if (mid >= 60) return `${Math.floor(mid / 60)} m ${String(mid % 60).padStart(2, '0')} s`
  return `${mid} s`
}

export default function PurpleTeam() {
  const [running, setRunning] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  // Real run responses from the backend, keyed by scenario id — replaces the
  // old hardcoded "38 s / 2 m 51 s" feedback after a run.
  const [runResults, setRunResults] = useState<Record<string, Scenario>>({})

  // Empty defaults: a failed request or a tenant with no purple-team data must
  // render an honest empty state, never the PayKraft demo fixtures.
  const scenarios = useApi<Scenario[]>(() => endpoints.purpleScenarios(), [])
  const readiness = useApi<ReadinessPoint[]>(() => endpoints.readiness(), [])

  // Live-derived stats — no hardcoded "4" / "49 s" / "94%" / "118" fallbacks.
  const lastReadiness = readiness.data[readiness.data.length - 1]
  const readinessScore = lastReadiness ? `${lastReadiness.score}%` : '—'
  const readinessHint = lastReadiness
    ? 'computed live from the purple-team pass rate'
    : 'no readiness data yet'
  const scenarioCount = scenarios.data.length
  const flaggedCount = scenarios.data.filter((s) => s.result === 'warning').length
  const scenarioHint = scenarioCount
    ? `${flaggedCount} flagged for tuning`
    : 'no scenarios recorded yet'
  const medianDetection = fmtMedian(
    scenarios.data.map((s) => toSeconds(runResults[s.id]?.detection ?? s.detection)).filter((x): x is number => x !== null),
  )

  // Really replays the scenario against the live detection pipeline; the
  // backend times detection + containment and returns the scored result.
  async function run(id: string) {
    setRunning(id)
    setDone(null)
    try {
      const res = (await endpoints.runScenario(id)) as Scenario
      setRunResults((prev) => ({ ...prev, [id]: res }))
      setDone(id)
      scenarios.reload()
      readiness.reload()
    } catch {
      setDone(null)
    } finally {
      setRunning(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="Purple Team Console"
        subtitle="The system attacks itself every night against the real detection pipeline, then publishes the score. Trust through evidence — one of the few platforms that closes this loop."
      >
        <div className="flex items-center gap-2">
          <DataSource live={scenarios.live} loading={scenarios.loading} />
          <span className="inline-flex items-center gap-1.5 font-mono text-xs text-ink-2">
            <CalendarClock size={13} aria-hidden /> nightly sweep 03:00 IST
          </span>
        </div>
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Defense readiness" value={readinessScore} hint={readinessHint} tone="good" />
        <StatTile label="Scenarios in rotation" value={String(scenarioCount)} hint={scenarioHint} tone="accent" />
        <StatTile label="Median detection" value={medianDetection} hint="across the scenario rotation" tone="good" />
        <StatTile label="Attacks simulated (30d)" value="—" hint="no simulation data yet" tone="neutral" />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card title="Scenario library" className="xl:col-span-2" padded={false}>
          <ul className="divide-y divide-border-subtle">
            {scenarios.data.length === 0 && (
              <li className="px-4 py-10 text-center font-mono text-xs text-ink-3">No scenarios recorded yet.</li>
            )}
            {scenarios.data.map((s) => (
              <li key={s.id} className="px-4 py-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <Swords size={15} className="text-series-4" aria-hidden />
                    <span className="font-mono text-sm font-semibold">{s.name}</span>
                    <StatusPill status={done === s.id ? 'passed' : s.result} />
                  </div>
                  <Button
                    size="sm" variant="outline"
                    onClick={() => run(s.id)}
                    disabled={running !== null}
                  >
                    {running === s.id
                      ? <><Loader2 size={13} className="animate-spin" aria-hidden /> simulating…</>
                      : <><Play size={13} aria-hidden /> Run now</>}
                  </Button>
                </div>
                <p className="mt-1.5 text-xs text-ink-2">{s.desc}</p>
                <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-ink-3">
                  <span>{runResults[s.id]?.lastRun ?? (done === s.id ? 'Just now' : s.lastRun)}</span>
                  <span>detection: <span className="text-ink-2">{runResults[s.id]?.detection ?? s.detection}</span></span>
                  <span>containment: <span className="text-ink-2">{runResults[s.id]?.containment ?? s.containment}</span></span>
                </div>
                {s.result === 'warning' && done !== s.id && (
                  <p className="mt-2 rounded-md border border-status-warning/25 bg-status-warning/5 px-3 py-2 text-xs text-ink-2">
                    Detection exceeded the 5-minute target. Detection agent proposed a new canary-file
                    rule — pending your approval in the Autonomy Console.
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <div className="space-y-4">
          <Card title="Readiness trend — 6 weeks">
            {readiness.data.length === 0 ? (
              <div className="flex h-[180px] items-center justify-center font-mono text-xs text-ink-3">
                No readiness data yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={readiness.data} margin={{ top: 8, right: 8, bottom: 0, left: -22 }}>
                  <CartesianGrid stroke="#21262d" vertical={false} />
                  <XAxis dataKey="week" tick={AXIS_TICK} axisLine={{ stroke: '#383f47' }} tickLine={false} />
                  <YAxis domain={[60, 100]} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: '#383f47' }} />
                  <Line name="readiness" type="monotone" dataKey="score" stroke="#199e70" strokeWidth={2} dot={{ r: 3, fill: '#199e70', stroke: '#161b22', strokeWidth: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
            <p className="mt-2 text-xs text-ink-3">Score = weighted pass rate × detection speed × containment speed, over the full scenario rotation.</p>
          </Card>

          <Card title="Why this matters">
            <p className="text-sm leading-relaxed text-ink-2">
              Every night the system runs its scenario set against the real detection pipeline and publishes
              the score. When you raise the autonomy dial, you're not trusting a promise — you're trusting an
              evidenced pass rate.
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}
