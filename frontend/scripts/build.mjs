import { cp, copyFile, mkdir, rm } from 'node:fs/promises'
import { build } from 'esbuild'

const outdir = 'dist'
await rm(outdir, { recursive: true, force: true })
await mkdir(outdir, { recursive: true })
await copyFile('index.html', `${outdir}/index.html`)
await cp('public', outdir, { recursive: true, force: true })

await build({
  entryPoints: ['src/main.tsx'],
  bundle: true,
  minify: true,
  sourcemap: true,
  format: 'esm',
  target: ['es2020'],
  outdir: `${outdir}/assets`,
  entryNames: 'app',
  assetNames: '[name]-[hash]',
  publicPath: '/assets/',
  loader: { '.svg': 'file' },
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL ?? ''),
  },
})
console.log('Frontend production bundle created in frontend/dist')
