"""Export generated artefacts for the TypeScript parity test and documentation.

Usage: ``python -m shared.contracts.export`` → writes ``shared/contracts/generated/``:
* ``enums.json``        — every closed set (Python is the reference)
* ``json_schema.json``  — JSON Schema of every model in SECTION_MODELS
* ``examples.json``     — resolved BACKBONE examples (useful as fixtures for mocks)
"""

from __future__ import annotations

import enum
import json
from pathlib import Path

from shared.contracts import models
from shared.contracts.backbone_examples import load_examples

OUT_DIR = Path(__file__).resolve().parent / "generated"


def enums() -> dict[str, list[str]]:
    return {
        name: [m.value for m in obj]
        for name, obj in vars(models).items()
        if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj.__module__ == models.__name__
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "enums.json").write_text(json.dumps(enums(), indent=2) + "\n")
    schema = {k: m.model_json_schema() for k, m in models.SECTION_MODELS.items()}
    (OUT_DIR / "json_schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (OUT_DIR / "examples.json").write_text(json.dumps(load_examples(), indent=2) + "\n")
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
