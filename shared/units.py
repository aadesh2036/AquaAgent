"""Unit conversions — the ONLY place conversions happen (BACKBONE §5.2).

Storage/internal (state layer) is WNTR-native SI. Public API/UI and the observation layer
(sensors, context, SensorWindow) use m and L/s (BACKBONE_ISSUES BI-07, BI-08).
Exact conversion factors (ft, in, gpm are defined exactly in SI):
  1 ft  = 0.3048 m
  1 in  = 0.0254 m
  1 US gal = 3.785411784e-3 m³  →  1 gpm = 6.30901964e-5 m³/s
"""

from __future__ import annotations

FT_TO_M = 0.3048
IN_TO_M = 0.0254
US_GAL_TO_M3 = 3.785411784e-3
GPM_TO_M3S = US_GAL_TO_M3 / 60.0
SECONDS_PER_DAY = 86_400

# --- flow -------------------------------------------------------------------


def m3s_to_lps(q_m3s: float) -> float:
    return q_m3s * 1000.0


def lps_to_m3s(q_lps: float) -> float:
    return q_lps / 1000.0


def lps_to_lpm(q_lps: float) -> float:
    """UI-only display of tap flow in L/min (§5.2)."""
    return q_lps * 60.0


def lpm_to_lps(q_lpm: float) -> float:
    return q_lpm / 60.0


def gpm_to_m3s(q_gpm: float) -> float:
    return q_gpm * GPM_TO_M3S


def gpm_to_lps(q_gpm: float) -> float:
    return m3s_to_lps(gpm_to_m3s(q_gpm))


# --- length / head ----------------------------------------------------------


def ft_to_m(x_ft: float) -> float:
    return x_ft * FT_TO_M


def m_to_ft(x_m: float) -> float:
    return x_m / FT_TO_M


def in_to_m(x_in: float) -> float:
    return x_in * IN_TO_M


def m_to_mm(x_m: float) -> float:
    return x_m * 1000.0


def mm_to_m(x_mm: float) -> float:
    return x_mm / 1000.0


# --- area -------------------------------------------------------------------


def m2_to_cm2(a_m2: float) -> float:
    """Leak area display only (§5.2)."""
    return a_m2 * 10_000.0


def cm2_to_m2(a_cm2: float) -> float:
    return a_cm2 / 10_000.0


# --- ratios -----------------------------------------------------------------


def fraction_to_pct(x: float) -> float:
    return x * 100.0


def pct_change(baseline: float, observed: float) -> float:
    """Percent change observed vs baseline. Raises on zero baseline (never divide silently)."""
    if baseline == 0:
        raise ZeroDivisionError("pct_change with zero baseline")
    return (observed - baseline) / abs(baseline) * 100.0


def level_pct(level_m: float, max_level_m: float) -> float:
    """Tank fill percentage for NetworkView.tank.level_pct, clamped to [0, 100]."""
    if max_level_m <= 0:
        raise ValueError("max_level_m must be > 0")
    return max(0.0, min(100.0, level_m / max_level_m * 100.0))


# --- time -------------------------------------------------------------------


def time_of_day_s(sim_time_s: int) -> int:
    """Demand pattern index (§5.3): sim_time_s mod 86400."""
    return int(sim_time_s) % SECONDS_PER_DAY


def clock_label(sim_time_s: int) -> str:
    """`HH:MM` label for the UI (§5.2)."""
    tod = time_of_day_s(sim_time_s)
    return f"{tod // 3600:02d}:{(tod % 3600) // 60:02d}"


# --- pump status representations (BACKBONE_ISSUES BI-20) ----------------------


def pump_status_to_int(status: str) -> int:
    """State-layer link status ('OPEN'/'CLOSED'/'ACTIVE') or UI ('ON'/'OFF') → 0/1."""
    s = status.upper()
    if s in {"OPEN", "ACTIVE", "ON"}:
        return 1
    if s in {"CLOSED", "OFF"}:
        return 0
    raise ValueError(f"unknown pump status {status!r}")


def pump_status_to_ui(status: str | int) -> str:
    on = status == 1 if isinstance(status, int) else pump_status_to_int(status) == 1
    return "ON" if on else "OFF"
