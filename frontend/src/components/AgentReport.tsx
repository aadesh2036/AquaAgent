// AgentReport — evidence report panel. Phase 1: no report exists yet (the detector is not trained).
import type { AgentReport as Report } from "@contracts";

export function AgentReport({ report }: { report: Report | null }): JSX.Element | null {
  if (!report) return null;
  return (
    <section className="cad-panel p-4 flex flex-col gap-2" aria-label="Evidence report">
      <div className="mono-label text-paler">// EVIDENCE REPORT{report.generated_by === "template" ? " · TEMPLATE EXPLANATION" : ""}</div>
      <div className="font-heading font-bold">{report.headline}</div>
      <p className="text-sm text-pale">{report.what_happened}</p>
      <p className="text-sm text-pale">{report.why_suspicious}</p>
    </section>
  );
}
