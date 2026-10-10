"""Tool specs (Converse toolConfig) + executors, exactly per BACKBONE §7.13.

Every executor reads an ``IncidentContext`` frozen at alarm time (SensorWindow + predictor response + Incident),
so tool results are derived from the firewall-safe pipeline only and never contain ground truth (§11).
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.contracts.models import (
    AGENT_TOOL_INPUTS,
    Incident,
    NetworkTopology,
    PredictorResponse,
    SensorWindow,
    SubmitReportInput,
)

TOOLS_T2D = ("get_incident", "get_sensor_history", "get_reconstruction", "get_candidate_locations",
             "get_network_element")
DESCRIPTIONS = {
    "get_incident": "The incident: detector result, localisation candidates, sensor/flow evidence "
    "(observed vs AI-expected) and demand context.",
    "get_sensor_history": "Last N readings (300-s steps) of one sensor: S1-S3 pressure in m, F1-F2 flow in L/s.",
    "get_reconstruction": "AI-estimated pressure (m) at every junction, with uncertainty, at the alarm time.",
    "get_candidate_locations": "Top-k probable leak locations (pipes/junctions) and the probable zone.",
    "get_network_element": "Static attributes of a node or link (type, zone, elevation, length, diameter).",
    "submit_report": "Submit the final incident report. Call exactly once, when done.",
}


@dataclass(frozen=True)
class IncidentContext:
    incident: Incident
    window: SensorWindow
    response: PredictorResponse
    topology: NetworkTopology


def _inline(node, defs: dict):
    """Resolve ``$ref``s (some Bedrock models reject ``$defs``) and drop pydantic titles."""
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline(defs[node["$ref"].split("/")[-1]], defs)
        return {k: _inline(v, defs) for k, v in node.items() if k not in ("title", "$defs")}
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node


def _schema(model) -> dict:
    s = model.model_json_schema()
    return _inline(s, s.get("$defs", {}))


def tool_config(include_what_if: bool = False) -> dict:
    """Converse `toolConfig` with JSON schemas generated from shared.contracts input models + submit_report."""
    names = [*TOOLS_T2D, *(("run_what_if",) if include_what_if else ())]
    tools = [
        {"toolSpec": {"name": n, "description": DESCRIPTIONS.get(n, n),
                      "inputSchema": {"json": _schema(AGENT_TOOL_INPUTS[n])}}}
        for n in names
    ]
    tools.append({"toolSpec": {"name": "submit_report", "description": DESCRIPTIONS["submit_report"],
                               "inputSchema": {"json": _schema(SubmitReportInput)}}})
    return {"tools": tools}


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 2)


def execute_tool(name: str, tool_input: dict, ctx: IncidentContext) -> dict:
    """Return JSON from §7 contracts, never prose. Never returns ground truth (§11)."""
    if name not in TOOLS_T2D:
        return {"error": f"unknown tool {name!r}"}
    args = AGENT_TOOL_INPUTS[name].model_validate(tool_input)
    inc = ctx.incident
    if getattr(args, "incident_id", inc.incident_id) != inc.incident_id:
        return {"error": f"unknown incident {args.incident_id!r}; current incident is {inc.incident_id!r}"}
    if name == "get_incident":
        return inc.model_dump(mode="json")
    if name == "get_sensor_history":
        sid = args.sensor_id
        steps = ctx.window.window[-args.last_n_steps:]
        if sid.startswith("F"):
            pts = [{"sim_time_s": s.sim_time_s, "value": _r(s.flow_lps.get(sid)), "unit": "L/s"} for s in steps]
        else:
            pts = [{"sim_time_s": s.sim_time_s, "value": _r(s.pressure_m.get(sid)), "unit": "m"} for s in steps]
        if all(p["value"] is None for p in pts):
            return {"error": f"unknown sensor {sid!r}; sensors are S1, S2, S3 (pressure) and F1, F2 (flow)"}
        return {"sensor_id": sid, "points": pts}
    if name == "get_reconstruction":
        rec = ctx.response.reconstruct
        return {
            "model_version": ctx.response.model_version,
            "sim_time_s": ctx.response.sim_time_s,
            "reconstruct": None if rec is None else {
                "pressure_m": {k: _r(v) for k, v in rec.pressure_m.items()},
                "pressure_std_m": {k: _r(v) for k, v in rec.pressure_std_m.items()},
            },
        }
    if name == "get_candidate_locations":
        loc = inc.localisation
        if loc is None:
            return {"error": "no localisation for this incident"}
        return loc.model_copy(update={"candidates": loc.candidates[: args.top_k]}).model_dump(mode="json")
    # get_network_element
    eid = args.element_id
    for n in ctx.topology.nodes:
        if n.node_id == eid:
            return {"element_kind": "node", **n.model_dump(mode="json", exclude={"x", "y"})}
    for lk in ctx.topology.links:
        if lk.link_id == eid:
            return {"element_kind": "link", **lk.model_dump(mode="json")}
    return {"error": f"unknown element {eid!r}"}
