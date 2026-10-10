"""Bedrock Converse loop with a mocked client (module 07 §6 step 5): success, invented number twice, throttling."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from api.agent.loop import run_converse
from api.agent.tools import IncidentContext, execute_tool, tool_config
from api.clients.agent_runner import AgentRunner
from shared.contracts.models import (
    Incident,
    LooEntry,
    NetworkTopology,
    PredictorResponse,
    Reconstruction,
    SensorWindow,
    WindowContext,
    WindowStep,
)

FIX = sorted((Path(__file__).parents[1] / "agent" / "fixtures" / "incidents").glob("inc_*.json"))[0]


@pytest.fixture()
def ctx() -> IncidentContext:
    inc = Incident.model_validate_json(FIX.read_text())
    steps = [
        WindowStep(sim_time_s=inc.created_sim_time_s - 300 * i, pressure_m={"S1": 40.0 + i, "S2": 30.0},
                   flow_lps={"F1": 12.5}, context=WindowContext(tank_level_m=2.0, pump_status=1,
                                                                 pump_flow_lps=20.0, reservoir_head_m=213.4,
                                                                 time_of_day_s=0))
        for i in reversed(range(4))
    ]
    window = SensorWindow(network_id=inc.network_id, sensor_layout_id=inc.sensor_layout_id, window=steps)
    resp = PredictorResponse(model_version="gnn_test", sim_time_s=inc.created_sim_time_s, latency_ms=1.0,
                             reconstruct=Reconstruction(pressure_m={"2": 50.123}),
                             leave_one_out={"S1": LooEntry(predicted_m=40.0, observed_m=41.0)})
    topo = NetworkTopology(network_id=inc.network_id, nodes=[], links=[], zones=[], taps=[], valves=[])
    return IncidentContext(inc, window, resp, topo)


def _submit(ctx: IncidentContext, extra: str = "") -> dict:
    inc = ctx.incident
    zone = inc.localisation.probable_zone
    return {
        "incident_id": inc.incident_id,
        "headline": f"Probable leak in zone {zone.zone_id}",
        "what_happened": f"Detector raised {inc.anomaly.status.value} with score {inc.anomaly.anomaly_score}.{extra}",
        "why_suspicious": "Readings deviate from the AI expectation.",
        "where": f"Probable leak zone {zone.zone_id} (score {zone.score}).",
        "evidence": [{"claim": "zone", "source_tool": "get_incident", "fields": ["localisation"]}],
        "recommended_actions": [{"priority": 1, "action": "Acoustic survey", "rationale": "top candidate"}],
        "confidence": "LOW",
    }


class FakeBedrock:
    def __init__(self, script: list) -> None:
        self.script, self.calls = list(script), []

    def converse(self, **kw):
        self.calls.append(kw)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        name, inp = item
        return {"output": {"message": {"role": "assistant", "content": [
            {"toolUse": {"toolUseId": f"t{len(self.calls)}", "name": name, "input": inp}}]}},
            "usage": {"inputTokens": 100, "outputTokens": 10}}


def test_tool_config_has_contract_schemas() -> None:
    names = [t["toolSpec"]["name"] for t in tool_config()["tools"]]
    assert names[-1] == "submit_report" and "get_sensor_history" in names and "run_what_if" not in names
    assert "$ref" not in str(tool_config())


def test_tools_return_contract_json(ctx) -> None:
    iid = ctx.incident.incident_id
    assert execute_tool("get_incident", {"incident_id": iid}, ctx)["incident_id"] == iid
    hist = execute_tool("get_sensor_history", {"sensor_id": "S1", "last_n_steps": 2}, ctx)
    assert [p["value"] for p in hist["points"]] == [41.0, 40.0] and hist["points"][0]["unit"] == "m"
    assert execute_tool("get_reconstruction", {"incident_id": iid}, ctx)["reconstruct"]["pressure_m"] == {"2": 50.12}
    assert len(execute_tool("get_candidate_locations", {"incident_id": iid, "top_k": 1}, ctx)["candidates"]) == 1
    assert "error" in execute_tool("get_incident", {"incident_id": "inc_other"}, ctx)


def test_loop_success_after_a_tool_call(ctx) -> None:
    fake = FakeBedrock([("get_sensor_history", {"sensor_id": "S1", "last_n_steps": 3}), ("submit_report", _submit(ctx))])
    rep, results, usage = run_converse(ctx, "model-x", "ap-south-1", client=fake)
    assert rep.generated_by == "bedrock" and rep.grounding_check.passed and usage["calls"] == 2
    assert rep.confidence.value in ("HIGH", "MEDIUM", "LOW") and len(results) == 3
    assert fake.calls[0]["inferenceConfig"]["temperature"] <= 0.2
    assert fake.calls[0]["toolConfig"]["toolChoice"] == {"any": {}}


def test_grounding_retry_then_success(ctx) -> None:
    fake = FakeBedrock([("submit_report", _submit(ctx, " About 1234 customers affected.")),
                        ("submit_report", _submit(ctx))])
    rep, _, usage = run_converse(ctx, "model-x", "ap-south-1", client=fake)
    assert rep.grounding_check.passed and usage["grounding_retries"] == 1
    fed_back = fake.calls[1]["messages"][2]["content"][0]["toolResult"]
    assert fed_back["status"] == "error" and "1234" in str(fed_back["content"])


def _runner(fake) -> AgentRunner:
    s = type("S", (), {"agent": "bedrock", "bedrock_model_id": "model-x", "region": "ap-south-1"})()
    return AgentRunner(s, client=fake)


def test_invented_number_twice_falls_back_to_template(ctx) -> None:
    bad = ("submit_report", _submit(ctx, " About 1234 customers affected."))
    runner = _runner(FakeBedrock([bad, bad]))
    rep = runner.diagnose(ctx)
    assert rep.generated_by == "template" and rep.grounding_check.passed
    assert "1234" in runner.last_run["fallback_reason"] and any("template" in c for c in rep.caveats)


def test_throttling_falls_back_to_template(ctx) -> None:
    from botocore.exceptions import ClientError

    err = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "Converse")
    rep = _runner(FakeBedrock([err])).diagnose(ctx)
    assert rep.generated_by == "template" and rep.grounding_check.passed


def test_template_mode_never_calls_bedrock(ctx) -> None:
    fake = FakeBedrock([])
    s = type("S", (), {"agent": "template", "bedrock_model_id": "model-x", "region": "ap-south-1"})()
    rep = AgentRunner(s, client=fake).diagnose(ctx)
    assert rep.generated_by == "template" and not fake.calls


@pytest.mark.bedrock
@pytest.mark.skipif(not os.environ.get("AQUA_BEDROCK_MODEL_ID"), reason="live Bedrock: set AQUA_BEDROCK_MODEL_ID")
def test_live_bedrock_report_is_grounded(ctx) -> None:
    rep, _, _ = run_converse(ctx, os.environ["AQUA_BEDROCK_MODEL_ID"], os.environ.get("AQUA_REGION", "ap-south-1"))
    assert rep.generated_by == "bedrock" and rep.grounding_check.passed
