"""AgentRunner: Bedrock Converse loop or TemplateReporter (BACKBONE §3.3, §9.6).

``AQUA_AGENT=template`` → deterministic template (instant, always grounded).
``AQUA_AGENT=bedrock``  → Converse tool loop with ``AQUA_BEDROCK_MODEL_ID`` (env only, may be an inference profile);
any failure (access, throttling, budget, grounding after one retry) falls back to the template, with a caveat.
"""

from __future__ import annotations

import logging
import time

from api.agent.grounding import check_grounding
from api.agent.template_reporter import CAVEATS, template_report
from api.agent.tools import IncidentContext
from shared.contracts.models import AgentReport

log = logging.getLogger("aquaagent.api.agent")


class AgentRunner:
    def __init__(self, settings, client=None) -> None:
        self.mode = settings.agent
        self.model_id = settings.bedrock_model_id
        self.region = settings.region or "ap-south-1"
        self.client = client
        self.last_run: dict = {}

    @property
    def bedrock_enabled(self) -> bool:
        return self.mode == "bedrock" and bool(self.model_id) and self.model_id != "unset"

    def info(self) -> dict:
        return {"mode": "bedrock" if self.bedrock_enabled else "template",
                "model_id": self.model_id if self.bedrock_enabled else None}

    def diagnose(self, ctx: IncidentContext) -> AgentReport:
        t0 = time.monotonic()
        if self.bedrock_enabled:
            from api.agent.loop import run_converse

            try:
                report, _, usage = run_converse(ctx, self.model_id, self.region, client=self.client)
                report.caveats = list(CAVEATS)
                self.last_run = {"generated_by": "bedrock", "model_id": self.model_id,
                                 "latency_s": round(time.monotonic() - t0, 2), **usage}
                log.info("bedrock report %s %s", ctx.incident.incident_id, self.last_run)
                return report
            except Exception as exc:  # access / throttling / budget / grounding → template (§9.6)
                log.warning("bedrock failed for %s, using template: %s", ctx.incident.incident_id, exc)
                fallback = f"AI narrative unavailable ({type(exc).__name__}); showing the template explanation"
                self.last_run = {"generated_by": "template", "fallback_reason": str(exc)[:300]}
        else:
            fallback = None
            self.last_run = {"generated_by": "template"}
        report = template_report(ctx.incident)
        if fallback:
            report.caveats.append(fallback)
        report.grounding_check = check_grounding(report, [ctx.incident.model_dump(mode="json")])
        self.last_run["latency_s"] = round(time.monotonic() - t0, 2)
        return report
