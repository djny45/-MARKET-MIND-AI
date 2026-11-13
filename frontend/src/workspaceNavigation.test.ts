import { describe, expect, it } from 'vitest'
import { resolveWorkspaceTabShortcut } from './workspaceNavigation'

describe('resolveWorkspaceTabShortcut', () => {
  it('maps Alt+number to the documented workspace tabs', () => {
    expect(resolveWorkspaceTabShortcut('1', true, null)).toBe('OVERVIEW')
    expect(resolveWorkspaceTabShortcut('7', true, null)).toBe('RUNS')
    expect(resolveWorkspaceTabShortcut('9', true, null)).toBe('RESEARCH')
  })

  it('supports cycling through the complete tab list', () => {
    expect(resolveWorkspaceTabShortcut('ArrowDown', true, null)).toBe('NEXT')
    expect(resolveWorkspaceTabShortcut('ArrowUp', true, null)).toBe('PREVIOUS')
  })

  it('ignores shortcuts without Alt and unsupported keys', () => {
    expect(resolveWorkspaceTabShortcut('1', false, null)).toBeNull()
    expect(resolveWorkspaceTabShortcut('0', true, null)).toBeNull()
    expect(resolveWorkspaceTabShortcut('x', true, null)).toBeNull()
  })

  it('does not hijack typing or editable controls', () => {
    expect(resolveWorkspaceTabShortcut('1', true, { tagName: 'INPUT' })).toBeNull()
    expect(resolveWorkspaceTabShortcut('2', true, { tagName: 'TEXTAREA' })).toBeNull()
    expect(resolveWorkspaceTabShortcut('3', true, { tagName: 'SELECT' })).toBeNull()
    expect(resolveWorkspaceTabShortcut('4', true, { isContentEditable: true })).toBeNull()
  })
})
