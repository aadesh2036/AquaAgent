import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { BlueprintBackground } from "./components/BlueprintBackground";
import { Landing } from "./pages/Landing";
import { Simulate } from "./pages/Simulate";
import { loadCity } from "./components/CityLink";

const City = lazy(() => loadCity().then((m) => ({ default: m.City })));

export function App(): JSX.Element {
  return (
    <>
      <BlueprintBackground />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/simulate" element={<Simulate />} />
        <Route path="/city" element={<Suspense fallback={<div className="p-10 font-mono-cad text-xs">LOADING…</div>}><City /></Suspense>} />
        <Route path="*" element={<Landing />} />
      </Routes>
    </>
  );
}
