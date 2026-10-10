"""Converse + toolConfig smoke call used by infra/scripts/14_bedrock_check.sh. Model id from env only.

Runs the real agent loop on one recorded incident fixture and prints the grounded report summary.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "incidents"


def main() -> int:
    model_id = os.environ.get("AQUA_BEDROCK_MODEL_ID")
    region = os.environ.get("AQUA_REGION") or os.environ.get("AWS_REGION")
    if not model_id or not region:
        print("set AQUA_BEDROCK_MODEL_ID and AQUA_REGION", file=sys.stderr)
        return 2
    from api.agent.loop import run_converse
    from api.agent.tools import IncidentContext
    from shared.contracts.models import Incident, NetworkTopology, PredictorResponse, SensorWindow

    inc = Incident.model_validate_json(sorted(FIXTURES.glob("inc_*.json"))[0].read_text())
    ctx = IncidentContext(
        inc,
        SensorWindow.model_construct(network_id=inc.network_id, sensor_layout_id=inc.sensor_layout_id, window=[]),
        PredictorResponse(model_version=inc.model_versions.predictor, sim_time_s=inc.created_sim_time_s,
                          latency_ms=0.0),
        NetworkTopology(network_id=inc.network_id, nodes=[], links=[], zones=[], taps=[], valves=[]),
    )
    report, _, usage = run_converse(ctx, model_id, region)
    print(f"headline: {report.headline}\ngrounded: {report.grounding_check.passed}\nusage: {usage}")
    return 0 if report.grounding_check.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
