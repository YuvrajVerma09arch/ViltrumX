import { describe, it, expect } from 'vitest'
import { cn, formatINR } from './utils'

describe('cn', () => {
  it('joins truthy classes and skips falsy ones', () => {
    expect(cn('a', false, 'b', undefined, null, 'c')).toBe('a b c')
  })
})

describe('formatINR', () => {
  it('formats crores', () => {
    expect(formatINR(3_20_00_000)).toBe('₹3.2 Cr')
    expect(formatINR(250_00_00_000)).toBe('₹250 Cr')
  })
  it('formats lakhs', () => {
    expect(formatINR(4_50_000)).toBe('₹4.5 L')
    expect(formatINR(1_00_000)).toBe('₹1 L')
  })
  it('formats small amounts with Indian grouping', () => {
    expect(formatINR(29_499)).toBe('₹29,499')
  })
})
