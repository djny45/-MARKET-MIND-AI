import { cp, copyFile, mkdir } from 'node:fs/promises'
import { context } from 'esbuild'

// Keep development output separate from `dist/` so `npm run dev` can never
// overwrite a production bundle (which build.mjs writes to `dist/`).
const outdir = 'dist-dev'
await mkdir(outdir, { recursive: true })
await copyFile('index.html', `${outdir}/index.html`)
await cp('public', outdir, { recursive: true, force: true })

const ctx = await context({
  entryPoints: ['src/main.tsx'],
  bundle: true,
  format: 'esm',
  target: ['es2020'],
  outdir: `${outdir}/assets`,
  entryNames: 'app',
  assetNames: '[name]-[hash]',
  publicPath: '/assets/',
  loader: { '.svg': 'file' },
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL ?? ''),
    'import.meta.env.VITE_BASE_PATH': JSON.stringify('/'),
  },
})
await ctx.watch()
const server = await ctx.serve({
  servedir: outdir,
  host: '0.0.0.0',
  port: Number(process.env.PORT || 5173),
})
console.log(`Development server listening on http://localhost:${server.port}`)
