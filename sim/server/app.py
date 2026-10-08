"""FastAPI app for BACKBONE §7.14.2. Returns full truth; the orchestrator enforces visibility.

Must not import boto3 (BACKBONE_ISSUES BI-11).

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations


def create_app():  # -> fastapi.FastAPI
    """Routes: GET /sim/health, POST /sim/session, POST /sim/session/{id}/event,
    POST /sim/session/{id}/advance, GET /sim/session/{id}/snapshot,
    POST /sim/session/{id}/fork_what_if, POST /sim/session/{id}/reset (§7.14.2)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")
