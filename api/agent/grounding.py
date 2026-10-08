"""Grounding check (BACKBONE §9.6, BI-14): every number must match a tool value ±0.5% or ±0.05.

Implementation: docs/modules/07_AQUAAGENT_BEDROCK.md
"""

from __future__ import annotations

from shared.contracts.models import AgentReport, GroundingCheck


def extract_numbers(text: str) -> list[str]:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")


def check_grounding(report: AgentReport, tool_results: list[dict]) -> GroundingCheck:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")
