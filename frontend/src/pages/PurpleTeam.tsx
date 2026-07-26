import { useState } from 'react'
import { Swords, Play, Loader2, CalendarClock } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { PageHeader, Card, StatusPill, Button, StatTile, DataSource } from '../components/ui'
import { PT_SCENARIOS, READINESS_HISTORY } from '../data/mock'
import { endpoints } from '../lib/api'
import { useApi } from '../lib/hooks'

const AXIS_TICK = { fill: '#6e7b8a', fontSize: 11, fontFamily: 'JetBrains Mono' }
const TOOLTIP_STYLE = {
  background: '#0d1117', border: '1px solid #30363d', borderRadius: 8,
  fontFamily: 'JetBrains Mono', fontSize: 12, color: '#e6edf3',
}

export default function PurpleTeam() {
  const [running, setRunning] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const scenarios = useApi<typeof PT_SCENARIOS>(() => endpoints.purpleScenarios(), PT_SCENARIOS)
  const readiness = useApi<typeof READINESS_HISTORY>(() => endpoints.readiness(), READINESS_HISTORY)

  // Really replays the scenario against the live detection pipeline; the
  // backend times detection + containment and returns the scored result.
  async function run(id: string) {
    setRunning(id)
    setDone(null)
    try {
      await endpoints.runScenario(id)
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
        <StatTile label="Defense readiness" value="94%" hint="last validated 03:24 IST today" tone="good" />
        <StatTile label="Scenarios in rotation" value="4" hint="1 flagged for tuning (PT-03)" tone="accent" />
        <StatTile label="Median detection" value="49 s" hint="across last night's sweep" tone="good" />
        <StatTile label="Attacks simulated (30d)" value="118" hint="all in isolated purple-team scope" tone="neutral" />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card title="Scenario library" className="xl:col-span-2" padded={false}>
          <ul className="divide-y divide-border-subtle">
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
                  <span>{done === s.id ? 'just now' : s.lastRun}</span>
                  <span>detection: <span className="text-ink-2">{done === s.id ? '38 s' : s.detection}</span></span>
                  <span>containment: <span className="text-ink-2">{done === s.id ? '2 m 51 s' : s.containment}</span></span>
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
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={readiness.data} margin={{ top: 8, right: 8, bottom: 0, left: -22 }}>
                <CartesianGrid stroke="#21262d" vertical={false} />
                <XAxis dataKey="week" tick={AXIS_TICK} axisLine={{ stroke: '#383f47' }} tickLine={false} />
                <YAxis domain={[60, 100]} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: '#383f47' }} />
                <Line name="readiness" type="monotone" dataKey="score" stroke="#199e70" strokeWidth={2} dot={{ r: 3, fill: '#199e70', stroke: '#161b22', strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
            <p className="mt-2 text-xs text-ink-3">Score = weighted pass rate × detection speed × containment speed, over the full scenario rotation.</p>
          </Card>

          <Card title="Why this matters">
            <p className="text-sm leading-relaxed text-ink-2">
              Last night the system ran the <span className="font-mono text-ink">exact chain from INC-042</span> against
              itself — and caught it in 41 seconds. When you raise the autonomy dial, you're not trusting a
              promise; you're trusting a nightly, evidenced pass rate.
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}
