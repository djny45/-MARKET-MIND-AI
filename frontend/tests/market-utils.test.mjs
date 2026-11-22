import test from 'node:test'
import assert from 'node:assert/strict'
import { formatSymbol, formatNumber, formatPercent, percentChange, hasNaN } from '../src/utils/market.mjs'

test('formatSymbol strips non-ticker characters and uppercases', () => {
  assert.equal(formatSymbol('btc-usdt:usd'), 'BTCUSDT:USD')
  assert.equal(formatSymbol('GOOG'), 'GOOG')
  assert.equal(formatSymbol(''), '')
})

test('formatNumber applies min and max fraction digits', () => {
  assert.equal(formatNumber(42), '42.00')
  assert.equal(formatNumber(3.14159, { maximumFractionDigits: 3 }), '3.142')
  assert.equal(formatNumber(0), '0.00')
})

test('formatPercent shows sign and two decimals', () => {
  assert.equal(formatPercent(0.023), '+0.02%')
  assert.equal(formatPercent(-1.5), '-1.50%')
  assert.equal(formatPercent(0), '+0.00%')
})

test('percentChange returns positive and negative deltas', () => {
  assert.equal(percentChange(100, 110), 10)
  assert.equal(percentChange(100, 90), -10)
  assert.equal(percentChange(100, 0), -100)
  assert.equal(percentChange(0, 100), 0)
})

test('hasNaN detects non-finite numbers', () => {
  assert.equal(hasNaN(1, 2, 3), false)
  assert.equal(hasNaN(1, NaN, 3), true)
  assert.equal(hasNaN('x'), true)
})
