import { Route, Routes } from "react-router-dom";
import { BlueprintBackground } from "./components/BlueprintBackground";
import { Landing } from "./pages/Landing";
import { Simulate } from "./pages/Simulate";

export function App(): JSX.Element {
  return (
    <>
      <BlueprintBackground />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/simulate" element={<Simulate />} />
        <Route path="*" element={<Landing />} />
      </Routes>
    </>
  );
}
