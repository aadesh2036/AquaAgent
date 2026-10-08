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
