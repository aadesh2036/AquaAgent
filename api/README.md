# api/ — `aquaagent-api` image (modules 07, 08)

- `app/`: FastAPI app, settings from canonical env vars (§10.4). **08**
- `routes/`: public API §7.14.1 (`/api/...`). **08**
- `session/`: event log, challenge lifecycle, visibility filter (truth stripped). **08**
- `clients/`: `SimClient` (§7.14.2), `PredictorClient` (local/aws), `AgentRunner` (07). **08/07**
- `pipeline/`: `SensorWindowBuffer` (the firewall boundary) → predictor → detector → localiser → `Incident`. **08**
- `agent/`: Bedrock Converse tools, loop, grounding check, TemplateReporter, prompts, fixtures. **07**
- `tests/`: firewall test (§11), schema conformance. **08**

```bash
uvicorn api.app.main:app --port 8080       # local (AQUA_MODE=local)
docker build -f api/Dockerfile -t aquaagent-api .
```

## Module 08 steps 1-2 (implemented)

Env: `AQUA_SIM_URL` (default `http://localhost:8000`), `AQUA_MODE` (`local` | `aws`; aws requires `X-Api-Key == AQUA_API_KEY`, OPTIONS exempt), `AQUA_CORS_ORIGINS` (comma-separated, default `http://localhost:5173`), `AQUA_CONFIG_DIR`.

Routes under `/api` (all responses carry `X-Aqua-Contract`): `GET /health`, `POST /session/reset`, `GET /network/topology`, `GET /network/state`, `POST /sim/step`, `POST /tap`, `POST /pipe/fault`, `POST /valve`. `/challenge/*` and `/agent/*` return 501 until module 08 step 5 / module 07.

- One in-memory session (`session/store.py`), created lazily or by `/session/reset`. Events act from the next 300-s step; the event text and tap/valve/visual_fault state show immediately.
- `session/visibility.py:to_network_view` is the only snapshot to `NetworkView` path (node bands: low < 20 m, critical < 10 m; reservoir/tank `demand_lps` keep their sign).
- Errors: unknown id or sim 4xx -> 422; sim unreachable/5xx -> 503. The api never imports `sim.` (tests only).
- Tests: `.venv/bin/python -m pytest api/tests -q`.
