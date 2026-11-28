import type { MarketKey } from "./market";

/**
 * Colour combination — "iris" theme.
 * Violet carries the product accent; each market desk keeps a distinct hue so
 * the single reactive scene can retint itself per desk.
 */
export const ACCENT = "#a78bfa";
export const ACCENT_BRIGHT = "#e0d7ff";
export const AQUA = "#4fe6d8";
export const MINT = "#5fe6a6";
export const ROSE = "#fd7f95";
export const AMBER = "#f6c76b";

export const FOCUS_COLOR: Record<string, string> = {
  gold: AMBER,
  silver: "#C7D0DB",
  crude: "#E07A5F",
  forex: AQUA,
  us: "#7fa6ff",
  india: MINT,
  crypto: "#F7931A",
  macro: "#c4b5fd",
};

export const STATUS_COLOR: Record<string, string> = {
  active: MINT,
  scanning: AQUA,
  debating: "#c4b5fd",
  idle: "#8a90ac",
  "risk-hold": ROSE,
};

export function focusLabel(focus: MarketKey | "macro"): string {
  if (focus === "gold") return "GOLD";
  if (focus === "silver") return "SILVER";
  if (focus === "crude") return "CRUDE";
  if (focus === "forex") return "FX";
  if (focus === "us") return "USA";
  if (focus === "india") return "INDIA";
  if (focus === "crypto") return "CRYPTO";
  return "MACRO";
}

export function formatUtcClock(iso: string): string {
  const date = new Date(iso);
  return `${date.getUTCHours().toString().padStart(2, "0")}:${date
    .getUTCMinutes()
    .toString()
    .padStart(2, "0")}:${date.getUTCSeconds().toString().padStart(2, "0")}`;
}

export function formatSignedPct(value: number, decimals = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function formatMoney(value: number, decimals = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}
