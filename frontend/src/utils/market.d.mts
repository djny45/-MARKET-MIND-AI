export declare function formatSymbol(symbol: unknown): string;
export declare function formatNumber(value: number, options?: { decimals?: number; maximumFractionDigits?: number }): string;
export declare function formatPercent(value: number): string;
export declare function percentChange(previous: number, current: number): number;
export declare function hasNaN(...values: unknown[]): boolean;
