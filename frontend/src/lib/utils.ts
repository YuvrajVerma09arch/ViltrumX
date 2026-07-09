/** Join class names, skipping falsy values. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}

/**
 * Format rupees the way an Indian founder reads them: ₹4.2 Cr, ₹18 L, ₹52,400.
 * Founder Mode renders every impact number through this.
 */
export function formatINR(amount: number): string {
  if (amount >= 1_00_00_000) {
    const cr = amount / 1_00_00_000
    return `₹${cr % 1 === 0 ? cr.toFixed(0) : cr.toFixed(1)} Cr`
  }
  if (amount >= 1_00_000) {
    const l = amount / 1_00_000
    return `₹${l % 1 === 0 ? l.toFixed(0) : l.toFixed(1)} L`
  }
  return `₹${new Intl.NumberFormat('en-IN').format(amount)}`
}

export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type Criticality = 'crown-jewel' | 'high' | 'medium' | 'low'
export type AutonomyLevel = 'L1' | 'L2' | 'L3' | 'L4'

export const AUTONOMY_LABELS: Record<AutonomyLevel, string> = {
  L1: 'Always auto',
  L2: 'Auto + notify',
  L3: 'Auto + auto-rollback',
  L4: 'Propose only',
}
