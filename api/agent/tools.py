"""Tool specs (Converse toolConfig) + executors, exactly per BACKBONE §7.13.

Implementation: docs/modules/07_AQUAAGENT_BEDROCK.md
"""

from __future__ import annotations

from shared.contracts.models import AGENT_TOOL_INPUTS  # noqa: F401


def tool_config(include_what_if: bool = False) -> dict:
    """Converse `toolConfig` with JSON schemas generated from shared.contracts input models + submit_report."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")


def execute_tool(name: str, tool_input: dict, ctx) -> dict:
    """Return JSON from §7 contracts, never prose. Never returns ground truth (§11)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")
