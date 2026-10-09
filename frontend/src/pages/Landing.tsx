import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Header } from "../components/Header";
import { HowItWorks } from "../components/landing/HowItWorks";
import { ArchitectureDeck, Footer, HonestLimits, Models, Telemetry } from "../components/landing/Sections";
import { CityLink } from "../components/CityLink";

const NAV = [
  { id: "overview", label: "[01] OVERVIEW" },
  { id: "how", label: "[02] HOW IT WORKS" },
  { id: "architecture", label: "[03] ARCHITECTURE" },
  { id: "models", label: "[04] MODELS" },
  { id: "limits", label: "[05] HONEST LIMITS" },
];

function ScrollNav(): JSX.Element {
  const [active, setActive] = useState("overview");
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [bar, setBar] = useState({ left: 0, width: 0 });

  useEffect(() => {
    const onScroll = (): void => {
      const y = window.scrollY + 120;
      let cur = NAV[0].id;
      for (const n of NAV) {
        const el = document.getElementById(n.id);
        if (el && el.offsetTop <= y) cur = n.id;
      }
      setActive(cur);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useLayoutEffect(() => {
    const b = refs.current[active];
    if (b) setBar({ left: b.offsetLeft, width: b.offsetWidth });
  }, [active]);

  return (
    <nav aria-label="Sections" className="relative flex gap-1">
      {NAV.map((n) => (
        <button key={n.id} ref={(el) => { refs.current[n.id] = el; }} onClick={() => document.getElementById(n.id)?.scrollIntoView({ behavior: "smooth" })}
          className={`px-3 py-4 font-mono-cad text-[11px] whitespace-nowrap ${active === n.id ? "text-white font-bold" : "text-pale"}`} aria-current={active === n.id ? "true" : undefined}>{n.label}</button>
      ))}
      <span className="absolute bottom-0 h-0.5 bg-white transition-all duration-300" style={{ left: bar.left, width: bar.width }} />
      <CityLink className="px-3 py-4 font-mono-cad text-[11px] whitespace-nowrap text-pale hover:text-white">[06] CITY VIEW (DEMO)</CityLink>
    </nav>
  );
}

export function Landing(): JSX.Element {
  return (
    <div className="min-h-screen">
      <div className="hidden lg:block fixed top-16 left-4 z-10 font-mono-cad text-[9px] text-white/50 pointer-events-none">DWG NO: AQ-NET-01 // NETWORK: net_epa_tutorial_v1</div>
      <div className="hidden lg:block fixed top-16 right-4 z-10 font-mono-cad text-[9px] text-white/50 pointer-events-none">SENSORS: 3 PRESSURE + 2 FLOW [+]</div>

      <Header tag="SIM://WNTR-1.5" center={<ScrollNav />}
        right={<Link to="/simulate" className="cad-btn-primary px-3 sm:px-4 py-2 font-mono-cad text-[11px] font-bold flex items-center gap-2 whitespace-nowrap">OPEN SIMULATOR <span aria-hidden="true" className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span></Link>} />

      <main>
        <section id="overview" className="pt-32 pb-16 sm:pt-44 sm:pb-24">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 text-center flex flex-col items-center gap-7">
            <div className="crosshair-corner blueprint-hatch-subtle bg-panel border border-white/40 px-4 py-2 flex items-center gap-2 font-mono-cad text-[10px] sm:text-[11px] uppercase tracking-wider">
              <span className="w-2 h-2 bg-white" />PHYSICS-GROUNDED LEAK DETECTION
            </div>
            <h1 className="font-heading font-bold text-4xl sm:text-5xl md:text-6xl leading-[1.08]">
              Water disappears underground.<br />
              <span className="font-normal text-pale">We work out <span className="relative inline-block font-hand text-5xl sm:text-6xl md:text-7xl text-white font-bold align-baseline">where.
                <svg viewBox="0 0 120 14" className="absolute left-0 -bottom-3 w-full" fill="none" aria-hidden="true"><path d="M 2 8 C 28 3, 75 4, 114 6" stroke="#fff" strokeWidth="1.8" /><path d="M 102 3 L 115 6 L 105 10" stroke="#fff" strokeWidth="1.5" /></svg>
              </span></span>
            </h1>
            <p className="text-pale text-base sm:text-lg max-w-2xl leading-relaxed">
              AquaAgent watches a pressurised water network through just five sensors. A model trained only on healthy days predicts what each sensor should read. When the readings stop fitting that prediction, it raises an alarm and shows the evidence.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 mt-2">
              <Link to="/simulate" className="cad-btn-primary px-6 py-3 font-mono-cad font-bold text-sm flex items-center justify-center gap-2">OPEN SIMULATOR <span aria-hidden="true" className="material-symbols-outlined">north_east</span></Link>
              <button className="cad-btn-secondary px-6 py-3 font-mono-cad font-bold text-sm flex items-center justify-center gap-2" onClick={() => document.getElementById("how")?.scrollIntoView({ behavior: "smooth" })}>SEE HOW IT WORKS <span aria-hidden="true" className="material-symbols-outlined">tune</span></button>
            </div>
          </div>
        </section>
        <Telemetry />
        <HowItWorks />
        <ArchitectureDeck />
        <Models />
        <HonestLimits />
      </main>
      <Footer />
    </div>
  );
}
