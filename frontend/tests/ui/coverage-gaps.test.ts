import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { expect, it } from 'vitest'

const srcDir = resolve(process.cwd(), 'src')
const sourceFiles = readdirSync(srcDir).filter(name => name.endsWith('.tsx'))
const source = sourceFiles.map(name => readFileSync(join(srcDir, name), 'utf8')).join('\n')
const packageJson = JSON.parse(readFileSync(resolve(process.cwd(), 'package.json'), 'utf8'))

describe('Coverage inventory guards (features genuinely absent from this build)', () => {
  it('confirms the real components that the UI suite covers', () => {
    expect(sourceFiles).toEqual(expect.arrayContaining([
      'App.tsx', 'AgentNetwork.tsx', 'AgentPositionMonitor.tsx', 'LearningLab.tsx', 'PriceChart.tsx',
    ]))
  })

  it('guards the absence of authentication: no login/logout/protected view/session expiry exists', () => {
    expect(source).not.toMatch(/\blogin\b|\blogout\b|\bsign[_-]?in\b|\bsign[_-]?out\b/i)
    expect(source).not.toMatch(/protected\s*route|require\s*auth|auth(?:entication|orization)?\s*(?:guard|token|flow)/i)
    expect(source).not.toMatch(/session\s*(?:expir|timeout)|jwt|bearer\s+/i)
  })

  it('guards the absence of a screener and a heatmap', () => {
    expect(source).not.toMatch(/\bscreener\b|\bheat\s*map\b/i)
  })

  it('guards the research-only constraint: no wallet, order routing or trade placement', () => {
    expect(source).not.toMatch(/connect\s*wallet|place\s*order|submit\s*order|order\s*rout/i)
    expect(source).toMatch(/NO EXECUTION LAYER|broker execution disabled/i)
  })

  it('the custom esbuild build remains the production build (no Vite migration)', () => {
    expect(packageJson.scripts.build).toContain('scripts/build.mjs')
    expect(packageJson.dependencies?.vite).toBeUndefined()
    expect(packageJson.dependencies?.vitest).toBeUndefined()
    expect(packageJson.scripts.test).toBe('node --test tests/*.test.mjs')
  })
})
