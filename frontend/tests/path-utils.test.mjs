import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeBasePath, rewriteHtmlRefs } from '../scripts/path-utils.mjs'

test('normalizeBasePath defaults to root', () => {
  assert.equal(normalizeBasePath(''), '/')
  assert.equal(normalizeBasePath('/'), '/')
})

test('normalizeBasePath adds leading and trailing slashes', () => {
  assert.equal(normalizeBasePath('repo-name'), '/repo-name/')
  assert.equal(normalizeBasePath('/repo-name'), '/repo-name/')
  assert.equal(normalizeBasePath('/repo-name/'), '/repo-name/')
})

test('rewriteHtmlRefs leaves root builds unchanged', () => {
  const html = '<link rel="stylesheet" href="/assets/app.css"/>'
  assert.equal(rewriteHtmlRefs(html, '/'), html)
})

test('rewriteHtmlRefs rewrites asset and page links for project sites', () => {
  const html = '<link href="/assets/app.css"/><script src="/assets/app.js"></script><a href="/market-terminal.html">x</a>'
  const result = rewriteHtmlRefs(html, '/MARKET-MIND-AI/')
  assert.match(result, /href="\/MARKET-MIND-AI\/assets\/app\.css"/)
  assert.match(result, /src="\/MARKET-MIND-AI\/assets\/app\.js"/)
  assert.match(result, /href="\/MARKET-MIND-AI\/market-terminal\.html"/)
})

test('rewriteHtmlRefs does not alter external URLs', () => {
  const html = '<a href="https://example.com/path">x</a>'
  assert.equal(rewriteHtmlRefs(html, '/repo/'), html)
})
