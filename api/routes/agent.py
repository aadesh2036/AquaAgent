"""Agent routes (BACKBONE §7.14.1; T1 template, T2d Bedrock with 20-s budget).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import AgentReport, AskRequest, AskResponse, DiagnoseRequest


def agent_diagnose(body: DiagnoseRequest) -> AgentReport:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def agent_ask(body: AskRequest) -> AskResponse:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
