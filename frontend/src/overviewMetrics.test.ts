import { describe, expect, it } from 'vitest'
import { summarizeStoredCoverage } from './overviewMetrics'

describe('summarizeStoredCoverage', () => {
  it('distinguishes an unavailable overview from an empty stored dataset', () => {
    expect(summarizeStoredCoverage(undefined)).toEqual({
      observations: null,
      distinctSources: null,
    })
    expect(summarizeStoredCoverage([])).toEqual({
      observations: 0,
      distinctSources: 0,
    })
  })

  it('sums observations and counts distinct normalized source labels', () => {
    expect(summarizeStoredCoverage([
      { observation_count: 12, sources: ['provider-a', ' provider-b '] },
      { observation_count: 8, sources: ['provider-a', 'provider-c'] },
    ])).toEqual({
      observations: 20,
      distinctSources: 3,
    })
  })

  it('ignores invalid counts and blank or malformed source labels', () => {
    expect(summarizeStoredCoverage([
      { observation_count: Number.NaN, sources: [' ', 'valid-source'] },
      { observation_count: -4, sources: undefined },
      { observation_count: 3.5, sources: ['valid-source'] },
    ])).toEqual({
      observations: 3.5,
      distinctSources: 1,
    })
  })
})
