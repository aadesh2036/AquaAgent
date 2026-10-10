// AgentReport — explainable-AI report for an AI incident (module 07, BACKBONE §7.13 / §9.6).
// Bedrock (Amazon Nova) writes the narrative through a forced submit_report tool; every number it writes is checked
// against the tool results (grounding badge). If Bedrock fails, the deterministic template is shown and labelled.
import { useEffect, useRef } from "react";
import { useSimStore } from "../state/simulationStore";
import type { ExplainReport } from "../api/ai";

const MODEL_NAMES: [RegExp, string][] = [
  [/nova-micro/, "Amazon Nova Micro"], [/nova-2-lite/, "Amazon Nova 2 Lite"], [/nova-lite/, "Amazon Nova Lite"],
  [/nova-pro/, "Amazon Nova Pro"], [/haiku/, "Claude Haiku"],
];
const modelName = (id?: string) => (id && MODEL_NAMES.find(([re]) => re.test(id))?.[1]) || id || "Bedrock";

function Section({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="font-mono-cad text-[10px] text-paler">{title}</div>
      <div className="text-[12px] leading-snug">{children}</div>
    </div>
  );
}

function Body({ report }: { report: ExplainReport }): JSX.Element {
  const bedrock = report.generated_by === "bedrock";
  const gc = report.grounding_check;
  const run = report.run;
  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`font-mono-cad text-[9px] px-1.5 py-0.5 ${bedrock ? "bg-white text-blueprint font-bold" : "border border-white/60"}`}>
          {bedrock ? `AI NARRATIVE · ${modelName(run?.model_id).toUpperCase()} ON AWS BEDROCK` : "TEMPLATE EXPLANATION"}
        </span>
        {gc && (
          <span title={gc.passed ? "Every number in this report was matched against the AI pipeline's tool results" : `Unmatched: ${gc.unmatched_numbers.join(", ")}`}
            className={`font-mono-cad text-[9px] px-1.5 py-0.5 border ${gc.passed ? "border-white/60" : "border-alarm text-alarm"}`}>
            {gc.passed ? "✓ ALL NUMBERS GROUNDED" : `⚠ ${gc.unmatched_numbers.length} UNGROUNDED NUMBER(S)`}
          </span>
        )}
        <span className={`font-mono-cad text-[9px] px-1.5 py-0.5 border ${report.confidence === "HIGH" ? "border-alarm text-alarm" : "border-white/60"}`}>
          CONFIDENCE {report.confidence}
        </span>
      </div>
      <div className="font-heading font-bold leading-snug">{report.headline}</div>
      <Section title="WHAT HAPPENED">{report.what_happened}</Section>
      <Section title="WHY THE AI THINKS SO">{report.why_suspicious}</Section>
      <Section title="WHERE TO LOOK">{report.where}</Section>
      {report.evidence.length > 0 && (
        <Section title="EVIDENCE">
          <ul className="list-disc pl-4 flex flex-col gap-0.5">
            {report.evidence.map((e, i) => (
              <li key={i}>{e.claim} <span className="font-mono-cad text-[9px] text-paler">[{e.source_tool}]</span></li>
            ))}
          </ul>
        </Section>
      )}
      <Section title="RECOMMENDED ACTIONS">
        <ol className="flex flex-col gap-1">
          {[...report.recommended_actions].sort((a, b) => a.priority - b.priority).map((a) => (
            <li key={a.priority} className="flex gap-2">
              <span className="font-mono-cad text-[10px] font-bold shrink-0">P{a.priority}</span>
              <span>{a.action}<span className="block text-[11px] text-paler">{a.rationale}</span></span>
            </li>
          ))}
        </ol>
      </Section>
      {report.caveats.length > 0 && (
        <ul className="text-[10px] text-paler leading-snug list-disc pl-4">
          {report.caveats.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      )}
      {run && (
        <div className="font-mono-cad text-[9px] text-paler">
          {report.incident_id}
          {run.latency_s !== undefined && ` · ${run.latency_s.toFixed(1)} s`}
          {run.inputTokens !== undefined && ` · ${run.inputTokens + (run.outputTokens ?? 0)} tokens`}
          {run.calls !== undefined && ` · ${run.calls} model call${run.calls === 1 ? "" : "s"}`}
        </div>
      )}
    </>
  );
}

export function AgentReport({ report }: { report: ExplainReport | null }): JSX.Element | null {
  const { explaining, explainError, explain, closeReport } = useSimStore();
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (explaining) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [explaining]);
  if (!report && !explaining && !explainError) return null;
  return (
    <section ref={ref} className="cad-panel p-4 flex flex-col gap-2.5" aria-label="Explainable AI report" aria-busy={!!explaining}>
      <div className="flex items-center justify-between gap-2">
        <div className="mono-label text-paler">// EXPLAINABLE AI REPORT</div>
        <div className="flex gap-1.5">
          {report && !explaining && (
            <button className="cad-btn-secondary px-2 py-0.5 font-mono-cad text-[9px]" onClick={() => void explain(report.incident_id, true)}>REGENERATE</button>
          )}
          <button className="cad-btn-secondary px-2 py-0.5 font-mono-cad text-[9px]" aria-label="Close report" onClick={closeReport}>CLOSE</button>
        </div>
      </div>
      {explaining ? (
        <p className="font-mono-cad text-[11px] text-pale aq-pulse">AI is analysing incident {explaining}… (Amazon Bedrock, up to 20 s)</p>
      ) : explainError ? (
        <p role="alert" className="text-[12px] text-alarm">Could not explain the incident: {explainError}</p>
      ) : report ? (
        <Body report={report} />
      ) : null}
    </section>
  );
}
