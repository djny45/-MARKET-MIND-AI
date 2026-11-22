import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { clickTab, setupApp } from './helpers'

const css = readFileSync(resolve(process.cwd(), 'src/style.css'), 'utf8')

describe('Responsive layout', () => {
  it('declares breakpoints for every major workspace surface', () => {
    const breakpoints = Array.from(css.matchAll(/@media\s*\(max-width:\s*(\d+)px\)/g), match => Number(match[1]))
    expect(new Set(breakpoints).size).toBeGreaterThanOrEqual(7)
    expect(breakpoints).toEqual(expect.arrayContaining([650, 850, 900, 950, 1000, 1050, 1100, 1250]))

    for (const rule of [
      '@media(max-width:1050px){.top-center{display:none}.sidebar{width:220px}',
      '@media(max-width:1250px){.toolbar{',
      '@media(max-width:950px){.toolbar{height:auto;min-height:52px;flex-wrap:wrap',
      '@media(max-width:650px){.overview-heading{flex-direction:column}.overview-grid{',
      '@media(max-width:900px){.agent-network-view{',
      '@media(max-width:900px){.agent-position-view{',
      '@media(max-width:1000px){.learning-stats{',
      '@media(max-width:850px){.volume-indicator-grid{',
    ]) {
      expect(css, `missing responsive rule: ${rule}`).toContain(rule)
    }
  })

  it('keeps the primary controls in the DOM at a simulated narrow viewport', async () => {
    const original = window.innerWidth
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    try {
      const { user } = setupApp()
      expect(await screen.findByRole('textbox', { name: 'Search instruments' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Configure/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /RUN WORKFLOW/ })).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /WATCHLIST/ }).length).toBeGreaterThan(0)
      await clickTab(user, 'RESEARCH')
      expect(await screen.findByRole('button', { name: 'RUN DEEP RESEARCH' })).toBeInTheDocument()
    } finally {
      Object.defineProperty(window, 'innerWidth', { configurable: true, value: original })
    }
  })

  it('DOCUMENTED LIMITATION: jsdom cannot evaluate CSS media queries', () => {
    // The narrow-viewport test above proves controls remain mounted and reachable;
    // computed breakpoint behaviour must be verified in a real browser.
    expect(window.matchMedia('(max-width: 650px)').matches).toBe(false)
  })
})
