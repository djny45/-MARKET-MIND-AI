import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { expect, it } from 'vitest'

const srcDir = resolve(process.cwd(), 'src')
const sourceFiles = readdirSync(srcDir).filter(name => name.endsWith('.tsx'))
const source = sourceFiles.map(name => readFileSync(join(srcDir, name), 'utf8')).join('\n')
const packageJson = JSON.parse(readFileSync(resolve(process.cwd(), 'package.json'), 'utf8'))

describe('Coverage inventory guards', () => {
  it('confirms the real components that the UI suite covers', () => {
    expect(sourceFiles).toEqual(expect.arrayContaining([
      'App.tsx', 'AgentNetwork.tsx', 'AgentPositionMonitor.tsx', 'LearningLab.tsx',
      'PriceChart.tsx', 'AuthPanel.tsx', 'CoverageTools.tsx',
    ]))
  })

  it('the authentication UI uses only session endpoints and exposes no backend secrets', () => {
    const auth = readFileSync(join(srcDir, 'AuthPanel.tsx'), 'utf8')
    expect(auth).toMatch(/\/api\/auth\/me/)
    expect(auth).toMatch(/\/api\/auth\/login/)
    expect(auth).toMatch(/\/api\/auth\/logout/)
    expect(auth).toMatch(/session expired|expired/i)
    expect(auth).not.toMatch(/api[_-]?key|client[_-]?secret|private[_-]?key|bearer\s+[A-Za-z0-9]/i)
    expect(auth).not.toMatch(/localStorage|sessionStorage/)
  })

  it('provides a screener and a coverage heatmap for stored observations only', () => {
    const tools = readFileSync(join(srcDir, 'CoverageTools.tsx'), 'utf8')
    expect(tools).toMatch(/screener/i)
    expect(tools).toMatch(/heatmap/i)
    expect(tools).toMatch(/MIN OBSERVATIONS|minimum observation/i)
    expect(tools).toMatch(/NOT LIVE MARKET DATA/i)
    expect(tools).not.toMatch(/price performance is|current market activity is|live quote/i)
  })

  it('guards the research-only constraint: no wallet, order routing or trade placement', () => {
    expect(source).not.toMatch(/connect\s*wallet|place\s*order|submit\s*order|order\s*rout/i)
    expect(source).toMatch(/NO EXECUTION LAYER|no execution layer/i)
  })

  it('the custom esbuild build remains the production build (no Vite migration)', () => {
    expect(packageJson.scripts.build).toContain('scripts/build.mjs')
    expect(packageJson.dependencies?.vite).toBeUndefined()
    expect(packageJson.dependencies?.vitest).toBeUndefined()
    expect(packageJson.scripts.test).toBe('node --test tests/*.test.mjs')
  })
})
