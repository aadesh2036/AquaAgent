"""Challenge lifecycle routes (BACKBONE §7.14.1).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import (
    ChallengeReveal,
    ChallengeStartRequest,
    ChallengeStartResponse,
    ChallengeStatusResponse,
)


def challenge_start(body: ChallengeStartRequest) -> ChallengeStartResponse:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def challenge_status() -> ChallengeStatusResponse:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def challenge_reveal() -> ChallengeReveal:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
