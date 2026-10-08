# sim/ — `aquaagent-sim` image (modules 01, 02)

- `engine/`: network build (official EPANET 2.2 tutorial `.inp`), leaks (junction + split-pipe), canonical snapshot mapping, mass balance, stepwise session. **Module 01**.
- `server/`: internal sim API, BACKBONE §7.14.2 (:8000). **Module 01**.
- `scenarios/`, `generate/`: ScenarioSpec sampling, batch runner, noise/sensor faults, validation, writer, merge + manifest. **Module 02**.
- `cli.py`: entrypoint `serve | generate | merge`.

```bash
docker build -f sim/Dockerfile -t aquaagent-sim .      # context = repo root
docker run -p 8000:8000 aquaagent-sim                   # serve
docker run aquaagent-sim generate --config config/generation/ds1.yaml --shard 0 --num-shards 8 --out s3://…
```
## Module 01 facts (G1)

- **WNTR 1.5.0** (pinned), `WNTRSimulator` only, Hazen-Williams, PDD (required 20 m, minimum 0 m). Network built from the BACKBONE §6 tables (no official `.inp` exists); `config/networks/net_epa_tutorial_v1.{json,inp}` are exported by `python -m sim.engine.network`.
- **Stepwise mode is the default** (one `WNTRSimulator` run per `advance`, 300-s steps, ~2-5 ms/step). `SimSession(replay_mode=True)` is the fallback: it rebuilds and replays the event log every call and gives identical results.
- **Event semantics:** an event recorded at `sim_time_s == t` (must equal the session time) takes effect from the NEXT 300-s step; the snapshot at t is never changed. Invalid events return 422 and are not logged.
- **Event params:** `TAP_SET` target T1-T3 `{"open": bool}`; `PIPE_FAULT` target pipe 1-8 `{"kind": "LEAK"|"BURST"|"CLOSE", "area_m2"?}` (defaults 1.5e-4 / 2e-3 m2, max 5e-3); `VALVE_SET` target V1 `{"open": bool}` (pipe 7 status); `PIPE_RESET` target pipe `{}`; `SPEED` logged only; `RESET` == reset.

```bash
make sim-smoke     # G1 smoke (24 h EPS, mass balance, leak, ms/step)
make sim-serve     # uvicorn on :8000
docker build -f sim/Dockerfile -t aquaagent-sim:dev . && docker run -p 8000:8000 aquaagent-sim:dev
```

Routes (BACKBONE §7.14.2; every response has `X-Aqua-Contract`): `GET /sim/health`, `POST /sim/session`, `POST /sim/session/{id}/event`, `POST /sim/session/{id}/advance` (1-20 steps), `GET /sim/session/{id}/snapshot`, `POST /sim/session/{id}/fork_what_if`, `POST /sim/session/{id}/reset`. Unknown session 404; bad input 422; WNTR failure 503.

```bash
SID=$(curl -s -XPOST localhost:8000/sim/session -H 'content-type: application/json' \
  -d '{"network_id":"net_epa_tutorial_v1","seed":1}' | python -c 'import sys,json;print(json.load(sys.stdin)["session_id"])')
curl -s -XPOST localhost:8000/sim/session/$SID/advance -H 'content-type: application/json' -d '{"steps":5}'
```

## Module 02 — data generation (ds1)

```bash
python -m sim.cli generate --config config/generation/ds1.yaml --shard 0 --num-shards 8 --out data/raw/ds1/shard=0/   # or s3://…
python -m sim.cli merge    --config config/generation/ds1.yaml --raw data/raw/ds1/ --out data/processed/ds1/
python -m sim.generate.calibrate                                                                                     # ~30 s, rewrites the `calibration:` block
```

- **Plan:** `plan_dataset(cfg)` -> 1,200 `ScenarioSpec`s, `sim_index` in a stratified-jitter interleave (every prefix and every `index % num_shards` slice is a mix of all 8 types). `seed = sim_seed(dataset_seed, i)` (SHA-256, 63 bit); auxiliary streams (`pipe_pos`, `demand`, `noise`) derive from it with `derive_seed`. Generator version `sim-0.2.0`.
- **Shard output:** `<out>/<table>/part-<shard:03d>.parquet` for `scenarios` (no `split` yet), `node_states`, `link_states`, `tank_states`, `pump_states`, `sensors`, `context`, `validation_log`. Exit code 0 iff >= 95% of the shard's sims are valid. Failed sims appear only in `validation_log`.
- **Merge:** assigns splits (70/15/15 per `scenario_type`, deterministic from `dataset_seed`; LEAK/BURST at `pipe:5` / `junction:6` -> test), writes `split=<s>/<table>/`, `graph/`, `validation_log/`, `manifest.json`. `--raw/--out/--out` accept local paths and `s3://` (fsspec/s3fs; credentials from the default chain, never boto3).
- **Reproducibility:** WNTR's C++ evaluator keys its Jacobian by pointer, so raw results jitter by <= 1.1e-13 m / 5e-16 m3/s between runs. The runner rounds to a fixed resolution (`runner.DECIMALS`: m 1e-4, m3/s 1e-7, m/s 1e-5, L/s 1e-4, m3 1e-3) so Parquet bytes are identical; a value can still flip only if it lies within the jitter of a rounding boundary (~1e-4 expected per sim). `validation_log.detail` prints solver-noise values only on failure.
- **Validation tolerances:** junction pressure >= -1e-6 m (operational scenarios only), tank level in [-1 mm, 6.096 m] (WNTR overshoots an emptying tank by ~1e-4 m), mass balance 1e-4 m3/s.
- **Severity:** `realised_leak_peak_m3s` (max total leak over the episode) / mean junction demand of the episode -> `<5%`, `5-15%`, `15-25%`, `>25%`. See `calibration:` in `config/generation/ds1.yaml` for the measured per-bucket distribution; the area ranges are not auto-changed.
- **Speed:** about 0.45 s per 24 h simulation on one core (WNTR solve + tabulation).
