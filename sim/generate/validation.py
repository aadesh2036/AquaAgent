"""Per-simulation validation checks → validation_log (BACKBONE §8.4).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

from shared.contracts.models import ValidationLogRow


def validate_simulation(spec, tables) -> list[ValidationLogRow]:
    """Run every check in models.VALIDATION_CHECKS; one row per check, pass or fail."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
