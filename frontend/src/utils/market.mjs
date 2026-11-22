/**
 * Pure market-data helpers shared by the terminal app and its tests.
 */
export function formatSymbol(symbol) {
  return String(symbol || "").replace(/[^A-Za-z0-9:@]/g, "").toUpperCase();
}

export function formatNumber(value, options = {}) {
  const decimals = options.decimals ?? 2;
  const maximumFractionDigits = options.maximumFractionDigits ?? decimals;
  const formatted = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: maximumFractionDigits,
  }).format(Number(value) || 0);
  return formatted;
}

export function formatPercent(value) {
  const n = Number(value) || 0;
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

export function percentChange(previous, current) {
  const prev = Number(previous);
  const curr = Number(current);
  if (!Number.isFinite(prev) || !Number.isFinite(curr) || prev === 0) return 0;
  return ((curr - prev) / Math.abs(prev)) * 100;
}

export function hasNaN(...values) {
  return values.some((value) => typeof value !== "number" || !Number.isFinite(value));
}
