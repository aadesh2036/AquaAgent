"""Converse loop: max 6 tool turns, temperature ≤ 0.2, forced submit_report (BACKBONE §9.6).

Implementation: docs/modules/07_AQUAAGENT_BEDROCK.md
"""

from __future__ import annotations

from shared.contracts.models import AgentReport, Incident

MAX_TURNS = 6
TEMPERATURE = 0.2
WALL_CLOCK_BUDGET_S = 20.0  # BACKBONE §7.14.1: API Gateway HTTP API hard limit is 30 s


def run_converse(incident: Incident, model_id: str, region: str) -> tuple[AgentReport, list[dict]]:
    """Return (report, tool_results_seen) — tool results feed the grounding check."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")
