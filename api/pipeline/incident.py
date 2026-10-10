"""Assemble Incident from AnomalyResult + LocalisationResult + evidence (BACKBONE §7.12). No ground truth.

Evidence is the AI's own view of the SensorWindow: ``baseline`` = what the predictor expects at a sensor from the
OTHER sensors (leave-one-out), ``observed`` = the noisy sensor reading. Values are rounded to 2 decimals so that a
report quoting them is matched exactly by the grounding check (§9.6).
"""

from __future__ import annotations

from shared import units
from shared.contracts.models import (
    AnomalyResult,
    ContextSummary,
    Evidence,
    FlowDelta,
    Incident,
    LocalisationResult,
    ModelVersions,
    PredictorResponse,
    PumpUiStatus,
    SensorDelta,
    SensorWindow,
)


def _r(x: float) -> float:
    return round(float(x), 2)


def _pct(baseline: float, observed: float) -> float:
    return _r(units.pct_change(baseline, observed)) if abs(baseline) > 1e-9 else 0.0


def build_incident(
    session_id: str,
    window: SensorWindow,
    response: PredictorResponse,
    anomaly: AnomalyResult,
    localisation: LocalisationResult | None,
    model_versions: dict,
) -> Incident:
    last = window.window[-1]
    t = last.sim_time_s
    driving = list(anomaly.driving_sensors)

    def order(sid: str) -> tuple[int, str]:  # driving sensors first, in detector order
        return (driving.index(sid) if sid in driving else len(driving), sid)

    sensor_deltas = [
        SensorDelta(
            sensor_id=sid,
            baseline_m=_r(e.predicted_m),
            observed_m=_r(e.observed_m),
            pct_change=_pct(e.predicted_m, e.observed_m),
        )
        for sid, e in sorted((response.leave_one_out or {}).items(), key=lambda kv: order(kv[0]))
        if e.observed_m is not None
    ]
    flow_deltas = [
        FlowDelta(
            sensor_id=sid,
            baseline_lps=_r(e.predicted_lps),
            observed_lps=_r(e.observed_lps),
            pct_change=_pct(e.predicted_lps, e.observed_lps),
        )
        for sid, e in sorted((response.leave_one_out_flow or {}).items(), key=lambda kv: order(kv[0]))
        if e.observed_lps is not None
    ]
    ctx = last.context
    anomaly = anomaly.model_copy(update={"anomaly_score": _r(anomaly.anomaly_score)})
    if localisation is not None:
        localisation = localisation.model_copy(
            update={
                "candidates": [
                    c.model_copy(update={"score": _r(c.score), "similarity": _r(c.similarity)})
                    for c in localisation.candidates
                ],
                "probable_zone": localisation.probable_zone.model_copy(
                    update={"score": _r(localisation.probable_zone.score)}
                ),
            }
        )
    return Incident(
        incident_id=f"inc_{session_id.removeprefix('sess_')}_{t}",
        session_id=session_id,
        created_sim_time_s=t,
        network_id=window.network_id,
        sensor_layout_id=window.sensor_layout_id,
        anomaly=anomaly,
        localisation=localisation,
        evidence=Evidence(
            sensor_deltas=sensor_deltas,
            flow_deltas=flow_deltas,
            context_summary=ContextSummary(
                time_of_day=units.clock_label(ctx.time_of_day_s),
                tank_level_m=_r(ctx.tank_level_m or 0.0),
                pump_status=PumpUiStatus(units.pump_status_to_ui(int(ctx.pump_status or 0))),
            ),
        ),
        model_versions=ModelVersions(**model_versions),
    )
