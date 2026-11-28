import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "MARKET MIND AI · 550-Agent Research Terminal",
  description:
    "Reactive 3D research terminal with simulated market data for gold, forex, USA and India markets, powered by 550 generated specialist agent profiles.",
};

export const viewport: Viewport = {
  themeColor: "#05060a",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-void text-ink antialiased">{children}</body>
    </html>
  );
}
