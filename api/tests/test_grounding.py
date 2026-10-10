"""Grounding check (BACKBONE §9.6) + TemplateReporter on the recorded incidents (G7 T1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.agent.grounding import check_grounding, extract_numbers
from api.agent.template_reporter import template_report
from shared.contracts.models import AgentReport, Confidence, EvidenceClaim, Incident, RecommendedAction

FIXTURES = sorted((Path(__file__).parents[1] / "agent" / "fixtures" / "incidents").glob("inc_*.json"))
TOOL = [{"evidence": {"sensor_deltas": [{"sensor_id": "S2", "baseline_m": 41.10, "observed_m": 38.40,
                                          "pct_change": -6.57}]},
         "flow": {"sensor_id": "F1", "observed_lps": 12.1},
         "anomaly": {"anomaly_score": 0.97, "first_flag_time_s": 42600},
         "candidates": [{"rank": 1, "location_id": "4", "zone_id": "Z2", "score": 0.81}],
         "context": {"time_of_day": "12:00"}}]


def _report(text: str) -> AgentReport:
    return AgentReport(
        incident_id="inc_x_1", headline="h", what_happened=text, why_suspicious="", where="",
        evidence=[EvidenceClaim(claim="c", source_tool="get_incident")],
        recommended_actions=[RecommendedAction(priority=1, action="a", rationale="r")],
        confidence=Confidence.LOW,
    )


def test_extract_numbers_skips_identifiers() -> None:
    nums = extract_numbers("S2 fell 6.57% to 38.40 m at 12:00 near pipe 4 (sig_ds1_202610091648, Z2), -2.7")
    assert nums == ["12:00", "6.57%", "38.40", "4", "-2.7"]


@pytest.mark.parametrize(
    "text",
    [
        "Pressure at S2 is 38.40 m vs 41.10 m expected.",       # exact
        "Pressure fell 6.57% at S2.",                            # sign ignored
        "Pressure at S2 is 38.5 m.",                             # within ±0.5 %
        "S2 is 2.70 m below expected.",                          # observed − baseline
        "Flow at F1 is 726 L/min.",                              # L/s → L/min
        "Anomaly probability 97%.",                              # fraction → %
        "First flagged at 11:50, now 12:00.",                    # clock labels from *_time_s and strings
        "Inspect pipe 4, rank 1 of 3.",                          # ids + ranks exempt
    ],
)
def test_grounded_sentences_pass(text: str) -> None:
    gc = check_grounding(_report(text), TOOL)
    assert gc.passed, gc.unmatched_numbers


@pytest.mark.parametrize(
    ("text", "bad"),
    [("About 150 customers are affected.", "150"), ("Water lost: 12.9 m3.", "12.9"), ("Since 13:15.", "13:15"),
     ("Score 0.70.", "0.70")],
)
def test_invented_numbers_fail(text: str, bad: str) -> None:
    gc = check_grounding(_report(text), TOOL)
    assert not gc.passed and gc.unmatched_numbers == [bad]


def test_fixtures_recorded() -> None:
    assert len(FIXTURES) >= 7


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_template_reports_are_grounded(path: Path) -> None:
    inc = Incident.model_validate_json(path.read_text())
    rep = template_report(inc)
    AgentReport.model_validate(rep.model_dump())
    assert rep.generated_by == "template" and rep.incident_id == inc.incident_id
    gc = check_grounding(rep, [inc.model_dump(mode="json")])
    assert gc.passed, gc.unmatched_numbers
    assert "probable leak zone" in rep.where.lower() or inc.localisation is None
    body = json.dumps(rep.model_dump(mode="json"))
    assert "LK_" not in body and "hidden" not in body and "truth" not in body  # §11 firewall
