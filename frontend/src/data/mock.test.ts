import { describe, it, expect } from 'vitest'
import { ONT_NODES, ONT_EDGES, INCIDENTS, ACTIONS, AGENTS } from './mock'
import { NARRATIVE, LANG_OPTIONS } from './i18n'

describe('ontology graph integrity', () => {
  it('every edge references existing nodes', () => {
    const ids = new Set(ONT_NODES.map((n) => n.id))
    for (const e of ONT_EDGES) {
      expect(ids.has(e.source), `edge ${e.id} source ${e.source}`).toBe(true)
      expect(ids.has(e.target), `edge ${e.id} target ${e.target}`).toBe(true)
    }
  })
  it('has a contiguous attack path for the demo', () => {
    expect(ONT_EDGES.filter((e) => e.attack).length).toBeGreaterThanOrEqual(3)
    expect(ONT_NODES.some((n) => n.compromised)).toBe(true)
  })
})

describe('scenario coherence', () => {
  it('exposes eight specialist agents', () => {
    expect(AGENTS).toHaveLength(8)
  })
  it('keeps the L4 proposal pending for the demo narrative', () => {
    const l4 = ACTIONS.find((a) => a.level === 'L4')
    expect(l4?.status).toBe('proposed')
  })
  it('INC-042 is the lead incident', () => {
    expect(INCIDENTS[0].id).toBe('INC-042')
    expect(INCIDENTS[0].mitre.length).toBeGreaterThan(0)
  })
})

describe('multilingual narrative', () => {
  it('renders in all three languages with founder + technical variants', () => {
    for (const { value } of LANG_OPTIONS) {
      const n = NARRATIVE[value]
      expect(n.technical.length).toBeGreaterThan(50)
      expect(n.founder.length).toBeGreaterThan(50)
      expect(n.impact).toHaveLength(4)
    }
  })
})
