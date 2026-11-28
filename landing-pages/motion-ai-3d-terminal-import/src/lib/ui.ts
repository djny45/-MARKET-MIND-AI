import type { MarketKey } from "./market";

export const FOCUS_COLOR: Record<string, string> = {
  gold: "#f2c46b",
  forex: "#5be9e0",
  us: "#8ab4ff",
  india: "#57e0a0",
  macro: "#a79bff",
};

export const STATUS_COLOR: Record<string, string> = {
  active: "#57e0a0",
  scanning: "#5be9e0",
  debating: "#a79bff",
  idle: "#7c879e",
  "risk-hold": "#ff7d88",
};

export function focusLabel(focus: MarketKey | "macro"): string {
  if (focus === "gold") return "GOLD";
  if (focus === "forex") return "FX";
  if (focus === "us") return "USA";
  if (focus === "india") return "INDIA";
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
