// ChallengePanel — TEST THE AI. Renders API values only; no hydraulic math (P1).
export function ChallengePanel({ onBreak }: { onBreak: () => void }): JSX.Element {
  return (
    <section className="cad-panel p-4 flex flex-col gap-3" aria-label="Test the AI">
      <div className="mono-label text-paler">// TEST THE AI</div>
      <p className="text-sm text-pale leading-relaxed">
        A leak is injected somewhere you cannot see. AquaAgent has to detect it from the five sensors, explain it, and then the answer is revealed.
      </p>
      <button className="cad-btn-primary py-2 font-mono-cad text-xs font-bold" disabled>START CHALLENGE</button>
      <p className="font-mono-cad text-[11px] text-paler leading-snug border-l-2 border-white/50 pl-3">
        The hid&#100;en-leak challenge goes live once the detector is trained (module 05). Until then, break the network yourself in BREAK IT.
      </p>
      <button className="cad-btn-secondary py-2 font-mono-cad text-[11px] font-bold" onClick={onBreak}>GO TO BREAK IT</button>
    </section>
  );
}
