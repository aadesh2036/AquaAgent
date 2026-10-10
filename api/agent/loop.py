"""Converse loop: max 6 tool turns, temperature ≤ 0.2, forced submit_report (BACKBONE §9.6).

The incident is sent in the first user turn (and counted as a ``get_incident`` result for grounding), so a typical
run is one or two model calls. The last allowed turn forces ``submit_report``. A grounding failure is fed back once
as an error result of ``submit_report``; the caller falls back to the template after that.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from api.agent.grounding import check_grounding
from api.agent.template_reporter import confidence_of
from api.agent.tools import IncidentContext, execute_tool, tool_config
from shared import units
from shared.contracts.models import AgentReport, Incident, SubmitReportInput

MAX_TURNS = 6
TEMPERATURE = 0.2
MAX_TOKENS = 1500
WALL_CLOCK_BUDGET_S = 20.0  # BACKBONE §7.14.1: API Gateway HTTP API hard limit is 30 s
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system_v1.md").read_text()
_clients: dict[str, object] = {}


class AgentError(RuntimeError):
    """Bedrock could not produce a grounded report (caller falls back to the template)."""


def bedrock_client(region: str):
    if region not in _clients:
        import boto3
        from botocore.config import Config

        _clients[region] = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(retries={"mode": "adaptive", "max_attempts": 3}, read_timeout=15, connect_timeout=3),
        )
    return _clients[region]


def run_converse(
    ctx: IncidentContext, model_id: str, region: str, client=None, budget_s: float = WALL_CLOCK_BUDGET_S
) -> tuple[AgentReport, list[dict], dict]:
    """Return (report, tool_results_seen, usage) — tool results feed the grounding check.

    ``report.grounding_check`` is filled here (orchestrator-owned, §9.6); raises AgentError if no grounded
    report is produced within MAX_TURNS / one grounding retry / the wall-clock budget."""
    client = client or bedrock_client(region)
    t0 = time.monotonic()
    incident_json = ctx.incident.model_dump(mode="json")
    labels = incident_labels(ctx.incident)
    results: list[dict] = [incident_json, labels]
    messages: list[dict] = [{
        "role": "user",
        "content": [{"text": "Incident (result of get_incident):\n" + json.dumps(incident_json)
                     + "\n\nlabels:\n" + json.dumps(labels)}],
    }]
    cfg = tool_config()
    usage = {"inputTokens": 0, "outputTokens": 0, "calls": 0, "grounding_retries": 0}
    retried = False
    for turn in range(MAX_TURNS):
        if time.monotonic() - t0 > budget_s:
            raise AgentError("wall-clock budget exceeded")
        force = turn == MAX_TURNS - 1
        resp = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig={**cfg, "toolChoice": {"tool": {"name": "submit_report"}} if force else {"any": {}}},
            inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": TEMPERATURE},
        )
        usage["calls"] += 1
        for k in ("inputTokens", "outputTokens"):
            usage[k] += resp.get("usage", {}).get(k, 0)
        msg = resp["output"]["message"]
        messages.append(msg)
        uses = [c["toolUse"] for c in msg["content"] if "toolUse" in c]
        if not uses:
            messages.append({"role": "user", "content": [{"text": "Use the tools; finish with submit_report."}]})
            continue
        replies = []
        for use in uses:
            if use["name"] == "submit_report":
                try:
                    sub = SubmitReportInput.model_validate(use["input"])
                except Exception as exc:  # schema error → let the model fix it
                    replies.append(_result(use, {"error": f"invalid report: {exc}"}, error=True))
                    continue
                report = AgentReport(  # id and confidence are orchestrator policy, not model opinion
                    **(sub.model_dump() | {"incident_id": ctx.incident.incident_id,
                                           "confidence": labels["confidence"]}),
                    generated_by="bedrock",
                )
                gc = check_grounding(report, results)
                report.grounding_check = gc
                if gc.passed:
                    return report, results, usage
                if retried:
                    raise AgentError(f"ungrounded numbers after retry: {gc.unmatched_numbers}")
                retried = True
                usage["grounding_retries"] += 1
                replies.append(_result(use, {
                    "error": "Report rejected: these numbers are not in any tool result: "
                    f"{gc.unmatched_numbers}. Remove or replace them with values copied from the tool "
                    "results, then call submit_report again."}, error=True))
            else:
                try:
                    out = execute_tool(use["name"], use["input"], ctx)
                except Exception as exc:
                    out = {"error": f"bad input: {exc}"}
                if "error" not in out:
                    results.append(out)
                replies.append(_result(use, out, error="error" in out))
        messages.append({"role": "user", "content": replies})
    raise AgentError("no submit_report within max turns")


def incident_labels(incident: Incident) -> dict:
    """Clock labels + the confidence policy, so the model never converts seconds or invents a confidence."""
    a = incident.anomaly
    clock = lambda t: units.clock_label(t) if t is not None else None  # noqa: E731
    return {
        "alarm_time": clock(incident.created_sim_time_s),
        "first_flagged": clock(a.first_flag_time_s),
        "confirmed": clock(a.confirmed_time_s),
        "confidence": confidence_of(incident).value,
    }


def _result(use: dict, payload: dict, error: bool = False) -> dict:
    r = {"toolUseId": use["toolUseId"], "content": [{"json": payload}]}
    if error:
        r["status"] = "error"
    return {"toolResult": r}
