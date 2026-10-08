"""Challenge lifecycle + reveal scoring (BACKBONE §7.14.1, BI-17).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import ChallengeReveal, Difficulty


class Challenge:
    def start(self, difficulty: Difficulty, sim_time_s: int) -> str:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")

    def reveal(self) -> ChallengeReveal:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
