import { cp, copyFile, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { build } from 'esbuild'

const outdir = 'dist'
const rawBase = process.env.VITE_BASE_PATH || '/'
const basePath = rawBase.startsWith('/') ? rawBase : `/${rawBase}`
const normalizedBase = basePath.endsWith('/') ? basePath : `${basePath}/`

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
  publicPath: `${normalizedBase}assets/`,
  loader: { '.svg': 'file' },
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL ?? ''),
    'import.meta.env.VITE_BASE_PATH': JSON.stringify(normalizedBase),
  },
})

// Project-site deployments (e.g. GitHub Pages at /<repo>/) need root-relative
// asset and page references rewritten to the configured base path. Local and
// self-hosted builds keep the default '/' and are left unchanged.
if (normalizedBase !== '/') {
  const rewrite = async (dir) => {
    const entries = await readdir(dir, { withFileTypes: true })
    for (const entry of entries) {
      const path = join(dir, entry.name)
      if (entry.isDirectory()) {
        await rewrite(path)
      } else if (entry.name.endsWith('.html')) {
        const html = await readFile(path, 'utf8')
        const updated = html.replace(/(href|src)=["']\//g, `$1="${normalizedBase}`)
        await writeFile(path, updated)
      }
    }
  }
  await rewrite(outdir)
  console.log(`Frontend base path: ${normalizedBase}`)
}
console.log('Frontend production bundle created in frontend/dist')
