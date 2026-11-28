import { TerminalShell } from "@/components/TerminalShell";
import { loadSnapshot } from "@/lib/snapshot";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const { snapshot, demo, reason } = await loadSnapshot();
  return <TerminalShell initialSnapshot={snapshot} demoReason={demo ? reason : null} />;
}
