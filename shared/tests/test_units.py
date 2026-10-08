"""Unit conversion tests (BACKBONE §5.2) — including the §6.1/§6.2 ft/gpm → SI values."""

import pytest

from shared import units as u


def test_flow_round_trip() -> None:
    assert u.lps_to_m3s(u.m3s_to_lps(0.0121)) == pytest.approx(0.0121)
    assert u.m3s_to_lps(0.00946) == pytest.approx(9.46)
    assert u.lps_to_lpm(1.0) == 60.0
    assert u.lpm_to_lps(u.lps_to_lpm(3.3)) == pytest.approx(3.3)


def test_backbone_section6_values() -> None:
    assert u.ft_to_m(700) == pytest.approx(213.36)
    assert u.ft_to_m(710) == pytest.approx(216.408)
    assert u.ft_to_m(830) == pytest.approx(252.984)
    assert u.in_to_m(14) == pytest.approx(0.3556)
    assert u.gpm_to_lps(150) == pytest.approx(9.46, abs=0.01)
    assert u.gpm_to_lps(200) == pytest.approx(12.62, abs=0.01)
    assert u.gpm_to_lps(600) == pytest.approx(37.85, abs=0.01)
    assert u.ft_to_m(150) == pytest.approx(45.72)


def test_area_and_length() -> None:
    assert u.m2_to_cm2(0.00015) == pytest.approx(1.5)
    assert u.cm2_to_m2(1.5) == pytest.approx(0.00015)
    assert u.m_to_mm(0.2032) == pytest.approx(203.2)
    assert u.mm_to_m(203.2) == pytest.approx(0.2032)
    assert u.m_to_ft(u.ft_to_m(20)) == pytest.approx(20)


def test_time() -> None:
    assert u.clock_label(43200) == "12:00"
    assert u.clock_label(86400 + 3660) == "01:01"
    assert u.time_of_day_s(90000) == 3600


def test_pct() -> None:
    assert u.pct_change(41.10, 38.40) == pytest.approx(-6.57, abs=0.01)
    assert u.level_pct(2.31, 6.096) == pytest.approx(37.9, abs=0.05)
    assert u.level_pct(10, 6.096) == 100.0
    with pytest.raises(ZeroDivisionError):
        u.pct_change(0, 1)


def test_pump_status() -> None:
    assert u.pump_status_to_int("OPEN") == 1
    assert u.pump_status_to_int("CLOSED") == 0
    assert u.pump_status_to_ui(1) == "ON"
    assert u.pump_status_to_ui("CLOSED") == "OFF"
    with pytest.raises(ValueError):
        u.pump_status_to_int("MAYBE")
