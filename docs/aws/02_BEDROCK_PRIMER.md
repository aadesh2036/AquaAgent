# 02 — Bedrock Primer for AquaAgent

> Prereq: [00_AWS_PRIMER.md](00_AWS_PRIMER.md). Implementation lives in [docs/modules/07_AQUAAGENT_BEDROCK.md](../modules/07_AQUAAGENT_BEDROCK.md).
> BACKBONE refs: §3.2 (Converse + toolConfig), §7.12 (Incident), §7.13 (tools, AgentReport), §9.6 (grounding), §10.1 (D1), §15 D2, G7.

## 1. Mental model in one diagram

```
 api container (AgentRunner)                         Amazon Bedrock (managed model API)
 ─────────────────────────────                       ─────────────────────────────────
 messages=[user: "Diagnose inc_3f9a1c_43200"]
 toolConfig={tools:[get_incident,…,submit_report]} ──Converse──▶  Claude decides: call a tool
                                                    ◀── stopReason=tool_use, content=[toolUse{name,input,toolUseId}]
 run the tool LOCALLY (our Python, §7 JSON only)
 append toolResult{toolUseId, json}              ──Converse──▶  Claude reads the result …
          … repeat ≤ 6 turns (§9.6) …
                                                    ◀── toolUse{name:"submit_report", input:{AgentReport fields}}
 grounding check (§9.6): every number ∈ tool results?
   pass → AgentReport(grounding_check.passed=true)
   fail → 1 retry with unmatched list → still fail → TemplateReporter (labelled)
```

Bedrock **runs** the model. We do not train anything on Bedrock. The tools run **in our code**: the model only *asks* for them.

## 2. The concepts that matter here

1. **What Bedrock is.** A pay-per-token API to foundation models (Claude here). There are no instances and no endpoint to delete. It is billed per input/output token.
2. **Model access.** Some accounts must enable or request access to a provider's models in the Bedrock console once per region. This is a **MANUAL STEP** (see `infra/scripts/14_bedrock_check.sh`).
3. **Model ID vs inference profile (BI-05).** Some models can only be called on-demand through an *inference profile* ID (cross-region routing). `14_bedrock_check.sh` lists both. Whichever ID works goes in `AQUA_BEDROCK_MODEL_ID`. It is **never hard-coded** (§10.4).
4. **Converse vs InvokeModel.** `InvokeModel` takes a provider-specific JSON body. `Converse` is one uniform message API across models, with built-in **tool use**. We use Converse (§3.2).
5. **Tool use via `toolConfig`.** You declare tools as JSON Schemas. The model replies with `toolUse` blocks, you run the tool and reply with `toolResult` blocks, and the loop continues until the model stops calling tools.
6. **Forced structured output.** We add a `submit_report` tool whose input schema is the `AgentReport` (minus `grounding_check`). The system prompt says "finish by calling submit_report". Its `input` *is* the report, so there is nothing to parse out of prose. `toolChoice` can also force a specific tool on the final turn (`{"tool":{"name":"submit_report"}}`, `<VERIFY: toolChoice support for the chosen model>`).
7. **Throttling and retries.** On `ThrottlingException`, retry with exponential backoff and jitter (botocore `retries={"mode":"adaptive","max_attempts":…}`). Our wall-clock budget is 25 s (BI-04). After that, use the template.
8. **Grounding wraps the loop (§9.6).** The orchestrator, not the model, checks that every number in the report exists in the tool results (±0.5% or ±0.05 abs). There is one retry, then `TemplateReporter`, clearly labelled in the UI.

## 3. Worked example: `get_incident` (BACKBONE §7.13)

**Request 1** (the Python shape; the CLI JSON is identical):

```python
client = boto3.client("bedrock-runtime", region_name=os.environ["AQUA_REGION"])
resp = client.converse(
    modelId=os.environ["AQUA_BEDROCK_MODEL_ID"],
    system=[{"text": open("api/agent/prompts/system_v1.md").read()}],
    messages=[{"role": "user", "content": [{"text": "Diagnose incident inc_3f9a1c_43200."}]}],
    inferenceConfig={"temperature": 0.1, "maxTokens": 1500},
    toolConfig={
        "tools": [
            {
                "toolSpec": {
                    "name": "get_incident",
                    "description": "Return the Incident (BACKBONE §7.12) for an incident_id. JSON only.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {"incident_id": {"type": "string"}},
                            "required": ["incident_id"],
                        }
                    },
                }
            },
            # … get_sensor_history, get_reconstruction, get_candidate_locations, get_network_element,
            # … submit_report (inputSchema = SubmitReportInput.model_json_schema())
        ]
    },
)
```

**Response 1** (abridged):

```json
{"stopReason": "tool_use",
 "output": {"message": {"role": "assistant", "content": [
   {"text": "I'll fetch the incident."},
   {"toolUse": {"toolUseId": "tooluse_abc123", "name": "get_incident",
                "input": {"incident_id": "inc_3f9a1c_43200"}}}]}}}
```

**Our code runs the tool** (`api/agent/tools.py::execute_tool`) → `Incident.model_dump(mode="json")`. Ground truth is never included (§11).

**Request 2**: append the assistant message unchanged, then a user message with the result:

```python
messages += [resp["output"]["message"],
             {"role": "user", "content": [{"toolResult": {
                 "toolUseId": "tooluse_abc123",
                 "content": [{"json": incident_json}],
                 "status": "success"}}]}]
resp = client.converse(modelId=…, system=…, messages=messages, toolConfig=…, inferenceConfig=…)
```

…the loop continues until `toolUse.name == "submit_report"`. Its `input` is validated with `SubmitReportInput`, and the orchestrator then adds `grounding_check`.

## 4. Why not Bedrock Agents / AgentCore (BACKBONE §3.2)

Those add managed orchestration, action groups and memory. That means more console setup, more IAM, and less control over the exact loop we need for the grounding check and the forced `submit_report`. A ~100-line Converse loop is easier to test with recorded fixtures (G7) and to fall back from. In the pitch, Agents/AgentCore is the "next step", not a requirement.

## 5. Commands, in order (expected output shape)

```bash
# 1. Which Anthropic models / profiles exist in my region?  (D1/D2)
infra/scripts/14_bedrock_check.sh
# table of modelId | ON_DEMAND/INFERENCE_PROFILE | ACTIVE
# WARN Choose one id from the tables above … then re-run

# 2. Verify a chosen id end-to-end (Converse "Reply with exactly: OK")
AQUA_BEDROCK_MODEL_ID=<id-from-table> infra/scripts/14_bedrock_check.sh
# model replied: OK
# OK Bedrock reachable. Saved model id + IAM ARNs.

# 3. Tighten IAM to that model and publish it to the api config
infra/scripts/03_iam_roles.sh && infra/scripts/11_ssm_params.sh
```

## 6. The five most common errors

| Error | Cause | Fix |
|---|---|---|
| `AccessDeniedException: You don't have access to the model…` | **Model access** not enabled. | MANUAL STEP: Bedrock console → Model access → enable → re-run 14. |
| `AccessDeniedException … not authorized to perform bedrock:InvokeModel` (from ECS) | **Permissions**: the task role ARNs don't cover the model or profile. | Re-run 14 (records ARNs) → 03. With an inference profile, both the profile ARN and the underlying model ARNs are needed (BI-05). |
| `ValidationException: Invocation of model ID … with on-demand throughput isn't supported` | **Model ID vs profile**: the model requires an inference profile. | Use the inference-profile ID from the second table. |
| `ResourceNotFoundException` / model not listed | **Region**: the model isn't offered in `$AWS_REGION`. | D1: use `us-east-1` unless the model is confirmed elsewhere (§10.1). |
| `ThrottlingException` | **Quota** (tokens/requests per minute). | Adaptive retries. Keep the loop ≤ 6 turns. Fall back to the template after the 25 s budget (BI-04). |

## 7. Cost notes and what to delete

Bedrock charges per token. There is nothing idle to delete. Keep prompts short, cap `maxTokens`, and limit to 6 turns. The 10-incident regression fixture (G7) costs about 10 short conversations per run, so don't run it in CI.

## 8. Check yourself

1. In the tool-use loop, who executes `get_incident`: Bedrock or our API?
2. Why is the report delivered as the *input* of a `submit_report` tool call instead of as text?
3. What happens if the report says "S2 dropped 7.1%" but the only tool value is `pct_change: -6.6`?

<details><summary>Answers</summary>

1. Our API. Bedrock only returns a `toolUse` request, and we run the tool and send back a `toolResult`.
2. The tool's JSON Schema forces exactly the `AgentReport` structure, which is validated by Pydantic. Nothing needs to be parsed from prose.
3. The grounding check flags `7.1` as unmatched, so `passed=false`. One retry is made with the unmatched list. If it still fails, `TemplateReporter` produces the report and the UI labels it "template explanation" (§9.6).
</details>
