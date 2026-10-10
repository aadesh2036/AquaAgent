"""Grounding check (BACKBONE §9.6, BI-14): every number must match a tool value ±0.5% or ±0.05.

Number pool = every numeric leaf of the tool results, plus these normalisations of it:
- units: L/s → L/min (×60), m³/s → L/s (×1000), fraction → % (×100), relative tolerance only;
- differences: ``observed_* − baseline_*`` / ``*_before_* − *_after_*`` of sibling fields (the "2.7 m below
  expected" sentence of §7.13);
- clock: every ``*_time_s`` / ``*_time_of_day_s`` int also yields its ``HH:MM`` label.
Signs are ignored ("fell 6.6 %" quotes ``pct_change: -6.6``).
Exempt: element IDs that are string values in the results, ``HH:MM`` labels in the pool, ranks/priorities 1–5.
Tokens glued to letters/underscores (``S2``, ``Z2``, ``sig_ds1_2026…``) are identifiers, not numbers.
"""

from __future__ import annotations

import re

from shared import units
from shared.contracts.models import AgentReport, GroundingCheck

REL_TOL = 0.005
ABS_TOL = 0.05
_CLOCK = re.compile(r"(?<![\w.:])([01]?\d|2[0-3]):([0-5]\d)(?![\w:])")
_NUM = re.compile(r"(?<![\w.])[-+−]?\d+(?:,\d{3})*(?:\.\d+)?(?![\w])%?")


def extract_numbers(text: str) -> list[str]:
    """Clock labels (``HH:MM``) first, then plain numbers (ints, decimals, signed, %) outside identifiers."""
    clocks = [m.group(0) for m in _CLOCK.finditer(text)]
    rest = _CLOCK.sub(" ", text)
    return clocks + [m.group(0) for m in _NUM.finditer(rest)]


def _walk(obj, pool: set[float], strings: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and k.endswith("time_s"):
                strings.add(units.clock_label(int(v)))
            _walk(v, pool, strings)
        for k, v in obj.items():  # sibling differences
            for a, b in (("observed_", "baseline_"), ("pressure_after_", "pressure_before_")):
                if k.startswith(a):
                    other = obj.get(b + k[len(a):])
                    if isinstance(v, (int, float)) and isinstance(other, (int, float)):
                        pool.add(float(v) - float(other))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk(v, pool, strings)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        pool.add(float(obj))
    elif isinstance(obj, str):  # numeric strings (pipe "4") are IDs: exempt as IDs, never numeric evidence
        strings.add(obj)


def _pool(tool_results: list[dict]) -> tuple[list[float], list[float], set[str]]:
    """(raw values, unit-converted values, strings). Converted values get the relative tolerance only."""
    base: set[float] = set()
    strings: set[str] = set()
    _walk(tool_results, base, strings)
    raw = sorted({abs(v) for v in base})
    converted = sorted({a * k for a in raw for k in (60.0, 1000.0, 100.0)})  # L/s→L/min, m³/s→L/s, →%
    return raw, converted, strings


def _matches(x: float, raw: list[float], converted: list[float]) -> bool:
    return any(abs(x - v) <= max(ABS_TOL, REL_TOL * v) for v in raw) or any(
        abs(x - v) <= REL_TOL * v for v in converted
    )


def report_texts(report: AgentReport) -> list[str]:
    """Model-written text (caveats are orchestrator-owned and number-free)."""
    out = [report.headline, report.what_happened, report.why_suspicious, report.where]
    out += [e.claim for e in report.evidence]
    out += [t for a in report.recommended_actions for t in (a.action, a.rationale)]
    return out


def check_grounding(report: AgentReport, tool_results: list[dict]) -> GroundingCheck:
    raw, converted, strings = _pool(tool_results)
    unmatched: list[str] = []
    for text in report_texts(report):
        for tok in extract_numbers(text):
            if ":" in tok:
                if tok not in strings and tok.zfill(5) not in strings:
                    unmatched.append(tok)
                continue
            num = tok.rstrip("%").replace(",", "").replace("−", "-").lstrip("+-")
            if num in strings:  # element id present in the results (pipe "4", junction "10")
                continue
            x = float(num)
            if x.is_integer() and 1 <= x <= 5 and not tok.endswith("%"):
                continue  # rank / priority
            if not _matches(x, raw, converted):
                unmatched.append(tok)
    return GroundingCheck(passed=not unmatched, unmatched_numbers=unmatched)
