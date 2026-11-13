export const WORKSPACE_TABS = [
  'OVERVIEW',
  'WORKFLOW',
  'AGENT_NETWORK',
  'AGENT_POSITIONS',
  'LEARNING',
  'WORKERS',
  'RUNS',
  'NEWS',
  'RESEARCH',
  'VALIDATION',
  'WATCHLIST',
] as const

export type WorkspaceTab = (typeof WORKSPACE_TABS)[number]

type ShortcutTarget = {
  tagName?: string
  isContentEditable?: boolean
}

export function resolveWorkspaceTabShortcut(
  key: string,
  altKey: boolean,
  target: ShortcutTarget | null,
): WorkspaceTab | 'NEXT' | 'PREVIOUS' | null {
  if (!altKey || target?.isContentEditable) return null

  const tagName = target?.tagName?.toUpperCase()
  if (tagName && ['INPUT', 'TEXTAREA', 'SELECT'].includes(tagName)) return null

  if (key === 'ArrowDown') return 'NEXT'
  if (key === 'ArrowUp') return 'PREVIOUS'
  if (/^[1-9]$/.test(key)) return WORKSPACE_TABS[Number(key) - 1] ?? null
  return null
}
