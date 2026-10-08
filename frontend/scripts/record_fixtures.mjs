#!/usr/bin/env node
// Records REAL API responses for mock mode (module 09). Needs the live stack:
//   sim:  .venv/bin/python -m sim.cli serve --port 8000
//   api:  AQUA_SIM_URL=http://localhost:8000 .venv/bin/python -m uvicorn api.app.main:app --port 8080
// Usage: node scripts/record_fixtures.mjs [baseUrl]   (default http://localhost:8080)
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const base = (process.argv[2] ?? process.env.VITE_API_BASE_URL ?? "http://localhost:8080").replace(/\/+$/, "");
const out = fileURLToPath(new URL("../src/api/fixtures/", import.meta.url));

async function call(method, path, body) {
  const res = await fetch(`${base}/api${path}`, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} -> HTTP ${res.status}`);
  return res.json();
}

const topology = await call("GET", "/network/topology");
const seq = [];
seq.push(await call("POST", "/session/reset", { seed: 1 }));
for (let i = 0; i < 8; i++) seq.push(await call("POST", "/sim/step", { steps: 1 }));
seq.push(await call("POST", "/tap", { tap_id: "T2", open: false }));
seq.push(await call("POST", "/sim/step", { steps: 1 }));
seq.push(await call("POST", "/tap", { tap_id: "T2", open: true }));
seq.push(await call("POST", "/pipe/fault", { link_id: "4", kind: "LEAK" }));
for (let i = 0; i < 8; i++) seq.push(await call("POST", "/sim/step", { steps: 1 }));

await mkdir(out, { recursive: true });
await writeFile(`${out}topology.json`, JSON.stringify(topology, null, 2) + "\n");
await writeFile(`${out}view.json`, JSON.stringify(seq[0], null, 2) + "\n");
await writeFile(`${out}views_sequence.json`, JSON.stringify(seq, null, 2) + "\n");
console.log(`recorded ${seq.length} frames from ${base} -> src/api/fixtures/`);
