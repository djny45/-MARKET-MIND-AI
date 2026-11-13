export type StoredCoverageRow = {
  observation_count?: number
  sources?: string[]
}

export type StoredCoverageSummary = {
  observations: number | null
  distinctSources: number | null
}

/** Summarize only values returned by the stored-data overview API. */
export function summarizeStoredCoverage(
  coverage: StoredCoverageRow[] | null | undefined,
): StoredCoverageSummary {
  if (!Array.isArray(coverage)) {
    return { observations: null, distinctSources: null }
  }

  const observations = coverage.reduce((total, row) => {
    const count = row?.observation_count
    return total + (typeof count === 'number' && Number.isFinite(count) && count > 0 ? count : 0)
  }, 0)
  const sources = new Set<string>()

  for (const row of coverage) {
    if (!Array.isArray(row?.sources)) continue
    for (const source of row.sources) {
      if (typeof source === 'string' && source.trim()) sources.add(source.trim())
    }
  }

  return { observations, distinctSources: sources.size }
}
