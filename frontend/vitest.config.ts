import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

const fromHere = (path: string) => fileURLToPath(new URL(path, import.meta.url))

// The UI suite renders the real React tree in jsdom. Two third-party libraries
// are replaced with lightweight local doubles because they require canvas/WebGL
// and layout APIs that jsdom does not implement:
//   - @xyflow/react: the graph views are asserted via their real node data and
//     their real click handlers; the double renders nodes as accessible DOM.
//   - lightweight-charts: PriceChart's headings/labels and its series wiring
//     are asserted through the double's spies.
// Production builds are unaffected: these aliases live only in this config.
export default defineConfig({
  resolve: {
    alias: {
      '@xyflow/react': fromHere('./tests/ui/mocks/xyflow.tsx'),
      'lightweight-charts': fromHere('./tests/ui/mocks/lightweight-charts.ts'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [fromHere('./tests/ui/setup.ts')],
    include: ['tests/ui/**/*.test.{ts,tsx}'],
    css: false,
    testTimeout: 10000,
    hookTimeout: 10000,
  },
})
