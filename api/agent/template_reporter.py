"""Deterministic AgentReport from an Incident — fallback, labelled 'template explanation' (BACKBONE §9.6).

Implementation: docs/modules/07_AQUAAGENT_BEDROCK.md
"""

from __future__ import annotations

from shared.contracts.models import AgentReport, Incident


def template_report(incident: Incident) -> AgentReport:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")
