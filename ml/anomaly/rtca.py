"""RTCA-style dual threshold detector (BACKBONE §9.3).

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations

from shared.contracts.models import AnomalyResult, ResidualFrame


class RTCADetector:
    """Instant |z|>k1; cumulative mean|z| over W > k2; ANOMALY after T consecutive both-flag steps."""

    def __init__(
        self,
        k1: float = 2.5,
        k2: float = 3.0,
        window_w: int = 6,
        consecutive_t: int = 3,
        thresholds_version: str = "",
    ) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")

    def update(self, frame: ResidualFrame) -> AnomalyResult:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")

    @classmethod
    def from_thresholds_json(cls, path: str) -> RTCADetector:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
