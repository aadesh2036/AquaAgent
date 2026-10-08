"""Extract and resolve the JSON examples embedded in BACKBONE.md (used by contract tests).

BACKBONE examples contain two kinds of placeholder that are resolved deterministically:
* ``{"…": "SensorWindow §7.8"}`` → the parsed example of that section;
* enum alternatives written as ``"A|B|C"`` → the first alternative ``"A"``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKBONE_PATH = REPO_ROOT / "BACKBONE.md"

# Order of ```json blocks in BACKBONE.md → contract key in models.SECTION_MODELS.
EXPECTED_BLOCKS: tuple[tuple[str, str], ...] = (
    ("6.4", "6.4"),
    ("7.1", "7.1"),
    ("7.2", "7.2"),
    ("7.3", "7.3"),
    ("7.4", "7.4"),
    ("7.6", "7.6"),
    ("7.8", "7.8"),
    ("7.9", "7.9.request"),
    ("7.9", "7.9.response"),
    ("7.10", "7.10.residual"),
    ("7.10", "7.10.anomaly"),
    ("7.11", "7.11"),
    ("7.12", "7.12"),
    ("7.13", "7.13"),
    ("7.14.1", "7.14.1.view"),
    ("7.14.1", "7.14.1.reveal"),
)

_PLACEHOLDER_KEY = "…"
_SECTION_HEADING = re.compile(r"^#{2,4}\s+(\d+(?:\.\d+)*)\b")
_PLACEHOLDER_REF = re.compile(r"§(\d+(?:\.\d+)*)")
_ENUM_ALTS = re.compile(r"^[A-Za-z_]+(\|[A-Za-z_]+)+$")


def extract_json_blocks(text: str) -> list[tuple[str, Any]]:
    """Return ``[(section, parsed_json), …]`` for every ```json fence, in document order."""
    out: list[tuple[str, Any]] = []
    section = ""
    in_block = False
    buf: list[str] = []
    for line in text.splitlines():
        if not in_block:
            m = _SECTION_HEADING.match(line)
            if m:
                section = m.group(1)
            if line.strip() == "```json":
                in_block, buf = True, []
        elif line.strip() == "```":
            in_block = False
            out.append((section, json.loads("\n".join(buf))))
        else:
            buf.append(line)
    return out


def _resolve(value: Any, by_section: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if set(value) == {_PLACEHOLDER_KEY}:
            ref = _PLACEHOLDER_REF.search(str(value[_PLACEHOLDER_KEY]))
            if not ref or ref.group(1) not in by_section:
                raise KeyError(f"unresolvable placeholder {value!r}")
            return _resolve(by_section[ref.group(1)], by_section)
        return {k: _resolve(v, by_section) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, by_section) for v in value]
    if isinstance(value, str) and _ENUM_ALTS.match(value):
        return value.split("|")[0]
    return value


def load_examples(path: Path = BACKBONE_PATH) -> dict[str, Any]:
    """Return ``{contract_key: resolved_example}`` for every BACKBONE JSON example."""
    blocks = extract_json_blocks(path.read_text(encoding="utf-8"))
    if [s for s, _ in blocks] != [s for s, _ in EXPECTED_BLOCKS]:
        raise AssertionError(
            "BACKBONE.md JSON blocks changed; update EXPECTED_BLOCKS. "
            f"found sections {[s for s, _ in blocks]}"
        )
    # Placeholders reference the *first* example in a section (§7.8 SensorWindow, §7.10 AnomalyResult
    # is referenced as "AnomalyResult §7.10" → we map §7.10 to the anomaly block explicitly).
    by_section: dict[str, Any] = {}
    for (section, key), (_, data) in zip(EXPECTED_BLOCKS, blocks, strict=True):
        if key == "7.10.residual":
            continue
        by_section.setdefault(section, data)
    resolved: dict[str, Any] = {}
    for (_, key), (_, data) in zip(EXPECTED_BLOCKS, blocks, strict=True):
        resolved[key] = _resolve(data, by_section)
    return resolved
