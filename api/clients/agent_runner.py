"""AgentRunner: Bedrock Converse loop or TemplateReporter (BACKBONE §3.3, §9.6).

Implementation: docs/modules/07_AQUAAGENT_BEDROCK.md
"""

from __future__ import annotations

from shared.contracts.models import AgentReport, Incident


class AgentRunner:
    def diagnose(self, incident: Incident) -> AgentReport:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")
