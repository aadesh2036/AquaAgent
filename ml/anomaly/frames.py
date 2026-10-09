"""Residual frames (BACKBONE §9.2, §7.10) — pydantic only, no torch, so the api image stays light."""

from __future__ import annotations

from shared.contracts.models import PredictorResponse, ResidualFrame, SensorWindow


def residual_frame(
    window: SensorWindow, response: PredictorResponse, sigmas: dict[str, float]
) -> ResidualFrame:
    """r_s = observed_s − LOO_prediction_s; z_s = r_s / σ_s (σ from val-normal). Missing readings are skipped."""
    if not isinstance(window, SensorWindow) or not isinstance(response, PredictorResponse):
        raise TypeError("residual_frame takes a SensorWindow and a PredictorResponse only (§11)")
    r: dict[str, float] = {}
    for s, e in (response.leave_one_out or {}).items():
        if e.observed_m is not None:
            r[s] = e.observed_m - e.predicted_m
    for f, e in (response.leave_one_out_flow or {}).items():
        if e.observed_lps is not None:
            r[f] = e.observed_lps - e.predicted_lps
    return ResidualFrame(
        sim_time_s=response.sim_time_s,
        residuals={s: round(v, 6) for s, v in r.items()},
        z={s: round(v / sigmas[s], 6) for s, v in r.items()},
    )
