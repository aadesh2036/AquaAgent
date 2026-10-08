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
Stepwise vs replay fallback decision: _to be recorded by module 01_. WNTR version: _pinned by module 01 (G1)_.
