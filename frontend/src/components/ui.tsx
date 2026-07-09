import type { ReactNode, ButtonHTMLAttributes } from 'react'
import { Crown, ShieldAlert, ShieldCheck, AlertTriangle, Info, type LucideIcon } from 'lucide-react'
import { cn, type Severity, type Criticality, type AutonomyLevel, AUTONOMY_LABELS } from '../lib/utils'

/* ── Buttons ─────────────────────────────────────────────────────────── */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
}

export function Button({ variant = 'primary', size = 'md', className, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={cn(
        'inline-flex cursor-pointer items-center justify-center gap-2 rounded-md font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40',
        size === 'sm' ? 'h-8 px-3 text-xs' : 'h-10 px-4 text-sm',
        variant === 'primary' && 'bg-accent text-bg hover:bg-accent-bright',
        variant === 'outline' && 'border border-border text-ink hover:border-ink-3 hover:bg-surface-2',
        variant === 'ghost' && 'text-ink-2 hover:bg-surface-2 hover:text-ink',
        variant === 'danger' && 'bg-status-critical/15 text-danger border border-status-critical/40 hover:bg-status-critical/25',
        className,
      )}
    />
  )
}

/* ── Surfaces ────────────────────────────────────────────────────────── */

export function Card({
  title, action, children, className, padded = true,
}: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return (
    <section className={cn('rounded-lg border border-border bg-surface', className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
          <h2 className="font-mono text-xs font-semibold tracking-widest text-ink-2 uppercase">{title}</h2>
          {action}
        </header>
      )}
      <div className={cn(padded && 'p-4')}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-mono text-xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-ink-2">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}

/* ── Stat tile (hero numbers; value wears ink, never a series color) ─── */

export function StatTile({
  label, value, hint, icon: Icon, tone = 'neutral',
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: LucideIcon
  tone?: 'neutral' | 'good' | 'warning' | 'critical' | 'accent'
}) {
  const toneDot = {
    neutral: 'bg-ink-3', good: 'bg-status-good', warning: 'bg-status-warning',
    critical: 'bg-status-critical', accent: 'bg-accent',
  }[tone]
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-ink-2">{label}</span>
        {Icon ? <Icon size={15} className="text-ink-3" aria-hidden /> : <span className={cn('h-2 w-2 rounded-full', toneDot)} aria-hidden />}
      </div>
      <div className="font-data mt-2 text-2xl font-bold">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-3">{hint}</div>}
    </div>
  )
}

/* ── Badges (icon + label — color never carries meaning alone) ───────── */

export function Badge({ tone = 'neutral', children, className }: {
  tone?: 'neutral' | 'green' | 'blue' | 'amber' | 'red' | 'purple'
  children: ReactNode
  className?: string
}) {
  const tones = {
    neutral: 'bg-surface-2 text-ink-2 border-border',
    green: 'bg-accent-dim text-accent-bright border-accent/30',
    blue: 'bg-info/10 text-info border-info/30',
    amber: 'bg-status-warning/10 text-status-warning border-status-warning/30',
    red: 'bg-status-critical/10 text-danger border-status-critical/35',
    purple: 'bg-series-4/10 text-series-4 border-series-4/30',
  }[tone]
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] font-medium whitespace-nowrap', tones, className)}>
      {children}
    </span>
  )
}

const SEVERITY_META: Record<Severity, { tone: 'red' | 'amber' | 'blue'; icon: LucideIcon }> = {
  critical: { tone: 'red', icon: ShieldAlert },
  high: { tone: 'red', icon: AlertTriangle },
  medium: { tone: 'amber', icon: AlertTriangle },
  low: { tone: 'blue', icon: Info },
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const { tone, icon: Icon } = SEVERITY_META[severity]
  return (
    <Badge tone={severity === 'high' ? 'amber' : tone}>
      <Icon size={11} aria-hidden /> {severity.toUpperCase()}
    </Badge>
  )
}

export function CriticalityBadge({ criticality }: { criticality: Criticality }) {
  if (criticality === 'crown-jewel') {
    return <Badge tone="amber"><Crown size={11} aria-hidden /> CROWN JEWEL</Badge>
  }
  const tone = criticality === 'high' ? 'red' : criticality === 'medium' ? 'blue' : 'neutral'
  return <Badge tone={tone}>{criticality.toUpperCase()}</Badge>
}

export function AutonomyBadge({ level }: { level: AutonomyLevel }) {
  const tone = { L1: 'neutral', L2: 'green', L3: 'blue', L4: 'purple' }[level] as 'neutral' | 'green' | 'blue' | 'purple'
  return <Badge tone={tone}>{level} · {AUTONOMY_LABELS[level]}</Badge>
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, { tone: 'green' | 'amber' | 'red' | 'blue' | 'neutral'; icon?: LucideIcon }> = {
    active: { tone: 'red', icon: ShieldAlert },
    contained: { tone: 'amber', icon: ShieldCheck },
    resolved: { tone: 'green', icon: ShieldCheck },
    executed: { tone: 'green', icon: ShieldCheck },
    'rolled-back': { tone: 'blue' },
    proposed: { tone: 'amber' },
    'awaiting approval': { tone: 'amber' },
    scheduled: { tone: 'blue' },
    passed: { tone: 'green', icon: ShieldCheck },
    warning: { tone: 'amber', icon: AlertTriangle },
    connected: { tone: 'green' },
    available: { tone: 'neutral' },
  }
  const { tone, icon: Icon } = map[status] ?? { tone: 'neutral' as const }
  return <Badge tone={tone}>{Icon && <Icon size={11} aria-hidden />}{status.toUpperCase()}</Badge>
}

/* ── Controls ────────────────────────────────────────────────────────── */

export function Segmented<T extends string>({ options, value, onChange, ariaLabel }: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  ariaLabel: string
}) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="inline-flex rounded-md border border-border bg-bg p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'cursor-pointer rounded px-2.5 py-1 font-mono text-xs font-medium transition-colors duration-150',
            value === o.value ? 'bg-surface-2 text-ink shadow-sm' : 'text-ink-3 hover:text-ink-2',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative h-5.5 w-10 cursor-pointer rounded-full border transition-colors duration-200',
        checked ? 'border-accent bg-accent-dim' : 'border-border bg-surface-2',
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 h-4 w-4 rounded-full transition-transform duration-200',
          checked ? 'translate-x-5 bg-accent' : 'translate-x-0.5 bg-ink-3',
        )}
      />
    </button>
  )
}

export function ProgressBar({ value, tone = 'accent' }: { value: number; tone?: 'accent' | 'warning' | 'critical' | 'info' }) {
  const bar = {
    accent: 'bg-accent', warning: 'bg-status-warning', critical: 'bg-status-critical', info: 'bg-info',
  }[tone]
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className={cn('h-full rounded-full transition-all duration-300', bar)} style={{ width: `${value}%` }} />
    </div>
  )
}

/* ── Table ───────────────────────────────────────────────────────────── */

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {head.map((h) => (
              <th key={h} className="px-3 py-2 text-left font-mono text-[11px] font-semibold tracking-wider text-ink-3 uppercase">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">{children}</tbody>
      </table>
    </div>
  )
}

export function Td({ children, className }: { children?: ReactNode; className?: string }) {
  return <td className={cn('px-3 py-2.5 align-middle', className)}>{children}</td>
}
