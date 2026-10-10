"""Deterministic AgentReport from an Incident — fallback, labelled 'template explanation' (BACKBONE §9.6).

Every number is copied from the Incident (formatted, never computed beyond the observed−baseline difference that the
grounding check also derives), so the report is always grounded.
"""

from __future__ import annotations

from shared import units
from shared.contracts.models import (
    AgentReport,
    Confidence,
    EvidenceClaim,
    Incident,
    RecommendedAction,
)

CAVEATS = [
    "Simulated network and synthetic sensor data",
    "Expected values come from the AI predictor using the other sensors; it can be wrong outside its training range",
    "Location is a probable leak zone / most likely pipe from physics signatures, never an exact location",
]


def _f(x: float) -> str:
    return f"{x:.2f}"


def _kind(c) -> str:
    return c.location_kind.value if hasattr(c.location_kind, "value") else str(c.location_kind)


def confidence_of(incident: Incident) -> Confidence:
    score = incident.anomaly.anomaly_score
    zone = incident.localisation.probable_zone.score if incident.localisation else 0.0
    if score >= 0.99 and zone >= 0.6:
        return Confidence.HIGH
    if score >= 0.9:
        return Confidence.MEDIUM
    return Confidence.LOW


def template_report(incident: Incident) -> AgentReport:
    a, ev, loc = incident.anomaly, incident.evidence, incident.localisation
    ctx = ev.context_summary
    driving = a.driving_sensors
    now = units.clock_label(incident.created_sim_time_s)

    if loc and loc.candidates:
        top = loc.candidates[0]
        headline = f"Probable leak in zone {loc.probable_zone.zone_id} (most likely {_kind(top)} {top.location_id})"
        where = (
            f"Probable leak zone {loc.probable_zone.zone_id} (zone score {_f(loc.probable_zone.score)}). "
            "Most likely: "
            + "; ".join(
                f"#{c.rank} {_kind(c)} {c.location_id} in {c.zone_id} (score {_f(c.score)}, "
                f"similarity {_f(c.similarity)})"
                for c in loc.candidates
            )
            + f". Method: {loc.method}, comparing the residual pattern with physics leak signatures "
            "simulated on the network map."
        )
    else:
        headline = "Abnormal hydraulic behaviour" + (f" near {', '.join(driving)}" if driving else "")
        where = "No location estimate; the deviation is strongest at " + (", ".join(driving) or "no single sensor")

    first = units.clock_label(a.first_flag_time_s) if a.first_flag_time_s is not None else now
    what = (
        f"At {now} the AI detector raised {a.status.value} with anomaly probability {_f(a.anomaly_score)}. "
        f"It first flagged the readings at {first}"
        + (f" and confirmed at {units.clock_label(a.confirmed_time_s)}" if a.confirmed_time_s is not None else "")
        + (f", driven by {', '.join(driving)}." if driving else ".")
    )

    lines, claims = [], []
    for i, d in enumerate(ev.sensor_deltas):
        diff = d.observed_m - d.baseline_m
        word = "below" if diff < 0 else "above"
        lines.append(
            f"Pressure at {d.sensor_id} reads {_f(d.observed_m)} m, {_f(abs(diff))} m {word} the "
            f"{_f(d.baseline_m)} m the AI expects from the other sensors ({d.pct_change:+.2f}%)."
        )
        claims.append(
            EvidenceClaim(
                claim=lines[-1], source_tool="get_incident", fields=[f"evidence.sensor_deltas[{i}]"]
            )
        )
    for i, d in enumerate(ev.flow_deltas):
        diff = d.observed_lps - d.baseline_lps
        word = "below" if diff < 0 else "above"
        lines.append(
            f"Flow at {d.sensor_id} reads {_f(d.observed_lps)} L/s, {_f(abs(diff))} L/s {word} the "
            f"{_f(d.baseline_lps)} L/s the AI expects ({d.pct_change:+.2f}%)."
        )
        claims.append(
            EvidenceClaim(claim=lines[-1], source_tool="get_incident", fields=[f"evidence.flow_deltas[{i}]"])
        )
    # keep the driving sensors (listed first by the Incident builder) in the summary sentence
    key = [ln for ln, d in zip(lines, [*ev.sensor_deltas, *ev.flow_deltas], strict=True) if d.sensor_id in driving]
    why = " ".join(key or lines[:2]) + (
        f" Demand context: time {ctx.time_of_day}, tank level {_f(ctx.tank_level_m)} m, pump {ctx.pump_status.value}."
    )
    claims.append(
        EvidenceClaim(
            claim=f"Detector status {a.status.value}, anomaly probability {_f(a.anomaly_score)}",
            source_tool="get_incident",
            fields=["anomaly.status", "anomaly.anomaly_score"],
        )
    )
    if loc:
        claims.append(
            EvidenceClaim(
                claim=f"Probable zone {loc.probable_zone.zone_id} with score {_f(loc.probable_zone.score)}",
                source_tool="get_candidate_locations",
                fields=["probable_zone"],
            )
        )

    target = (
        f"{_kind(loc.candidates[0])} {loc.candidates[0].location_id}"
        if loc and loc.candidates
        else ("the area around " + ", ".join(driving) if driving else "the network")
    )
    actions = [
        RecommendedAction(
            priority=1,
            action=f"Dispatch a crew for an acoustic leak survey of {target}",
            rationale="It is the top-ranked candidate; listening on the pipe confirms or rules out a leak quickly.",
        ),
        RecommendedAction(
            priority=2,
            action=(
                f"Run a step test in zone {loc.probable_zone.zone_id} by closing boundary valves in turn"
                if loc
                else "Run a step test by closing boundary valves in turn"
            ),
            rationale="If the deviation disappears when a section is isolated, the loss is inside that section.",
        ),
        RecommendedAction(
            priority=3,
            action="Check the driving sensors for calibration or communication faults"
            + (f" ({', '.join(driving)})" if driving else ""),
            rationale="A faulty logger can mimic a pressure drop; a field check rules this out.",
        ),
    ]
    return AgentReport(
        incident_id=incident.incident_id,
        headline=headline,
        what_happened=what,
        why_suspicious=why,
        where=where,
        evidence=claims,
        recommended_actions=actions,
        confidence=confidence_of(incident),
        caveats=list(CAVEATS),
        generated_by="template",
    )
