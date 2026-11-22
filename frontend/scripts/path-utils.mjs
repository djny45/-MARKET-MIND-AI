export function normalizeBasePath(raw) {
  const value = String(raw || '').trim()
  if (!value || value === '/') return '/'
  const rooted = value.startsWith('/') ? value : `/${value}`
  return rooted.endsWith('/') ? rooted : `${rooted}/`
}

export function rewriteHtmlRefs(html, basePath) {
  if (!basePath || basePath === '/') return html
  return html.replace(/(href|src)=["']\//g, `$1="${basePath}`)
}
