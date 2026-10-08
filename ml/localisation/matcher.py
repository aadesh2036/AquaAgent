"""Online cosine matcher with zone aggregation (BACKBONE §9.4, §7.11).

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations

from shared.contracts.models import LocalisationResult, ResidualFrame


class SignatureMatcher:
    def __init__(self, signatures_path: str, network_config_path: str) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")

    def rank(self, frames: list[ResidualFrame], top_k: int = 5) -> LocalisationResult:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
