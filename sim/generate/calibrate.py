"""Leak-size calibration -> config/generation/ds1.yaml `calibration` (BACKBONE §8.1, G2).

For each of the 14 fault locations x the geometric midpoint of each bucket's area range, run one
deterministic episode (default diurnal profile, no noise, leak from 12:00 to the end, pipe split 0.5)
and compute the realised peak leak flow as % of the episode's mean junction demand.

The area ranges are NEVER changed here. If a bucket's median falls outside its target band the
result is flagged (`median_in_band: false`) and reported, for a human to decide (BACKBONE §16).

Run: `python -m sim.generate.calibrate [--config config/generation/ds1.yaml] [--no-write]`
Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import numpy as np

from shared.contracts import ids
from shared.contracts.models import (
    FaultSpec,
    FaultType,
    LocationKind,
    NoiseSpec,
    Operations,
    ScenarioSpec,
    ScenarioType,
)
from sim.engine import network as net
from sim.generate.runner import leak_metrics, load_config, simulate
from sim.scenarios.sampler import DISCHARGE_COEFF, GENERATOR_VERSION, config_hash

BANDS_PCT = {  # target realised leak as % of mean system demand (matches SeverityBucket)
    "SMALL_LEAK": (0.0, 5.0),
    "MEDIUM_LEAK": (5.0, 15.0),
    "LARGE_LEAK": (15.0, 25.0),
    "PIPE_BURST": (25.0, math.inf),
}
FAULT_START_S = 43_200


def _spec(cfg: dict, idx: int, scenario: ScenarioType, kind: LocationKind, loc: str, area: float) -> ScenarioSpec:
    prof = net.DEFAULT_DEMAND_PROFILE.model_copy(update={"noise_sigma": 0.0})
    spec = ScenarioSpec(
        simulation_id=ids.simulation_id("cal", idx),
        network_id=cfg["network_id"],
        sensor_layout_id=cfg["sensor_layout_id"],
        seed=idx,
        demand_profile=prof,
        operations=Operations(tank_init_level_m=net.TANK_INIT_LEVEL_M),
        scenario_type=scenario,
        faults=[
            FaultSpec(
                fault_id="f0",
                fault_type=FaultType.BURST if scenario == ScenarioType.PIPE_BURST else FaultType.LEAK,
                location_kind=kind,
                location_id=loc,
                position=0.5 if kind == LocationKind.PIPE else None,
                leak_area_m2=area,
                discharge_coeff=DISCHARGE_COEFF,
                start_s=FAULT_START_S,
            )
        ],
        noise=NoiseSpec(**{k: cfg["noise"][k] for k in ("pressure_sigma_m", "flow_sigma_lps", "missing_rate")}),
        config_hash="sha256:" + "0" * 64,
        generator_version=GENERATOR_VERSION,
    )
    return spec.model_copy(update={"config_hash": config_hash(spec)})


def measure(cfg: dict) -> dict:
    fl = cfg["fault_locations"]
    locs = [(LocationKind.JUNCTION, j) for j in fl["junctions"]] + [(LocationKind.PIPE, p) for p in fl["pipes"]]
    out: dict = {}
    idx = 0
    for name, (band_lo, band_hi) in BANDS_PCT.items():
        lo, hi = cfg["leak_area_m2"][name]
        area = math.sqrt(lo * hi)
        pcts = []
        for kind, loc in locs:
            snaps = simulate(_spec(cfg, idx, ScenarioType(name), kind, loc, area))
            idx += 1
            peak, mean_demand = leak_metrics(snaps)
            pcts.append(100.0 * peak / mean_demand)
        arr = np.array(pcts)
        med = float(np.median(arr))
        out[name] = {
            "area_m2_midpoint": float(f"{area:.4g}"),
            "target_pct": [band_lo, None if math.isinf(band_hi) else band_hi],
            "min_pct": round(float(arr.min()), 1),
            "median_pct": round(med, 1),
            "max_pct": round(float(arr.max()), 1),
            "frac_in_band": round(float(np.mean((arr >= band_lo) & (arr < band_hi))), 2),
            "median_in_band": bool(band_lo <= med < band_hi),
        }
    return out


def _yaml_block(results: dict) -> str:
    lines = [
        "calibration:       # written by `python -m sim.generate.calibrate` (module 02, G2); ranges above are NOT auto-changed",
        "  done: true",
        "  method: \"14 locations x geometric-midpoint area per bucket, fault at 12:00 to end, default diurnal profile, no noise, pipe split 0.5; realised = peak total leak flow / mean junction demand of the episode\"",
        "  realised_pct_of_system_demand:",
    ]
    for name, r in results.items():
        tgt = f"[{r['target_pct'][0]:g}, {'null' if r['target_pct'][1] is None else format(r['target_pct'][1], 'g')}]"
        lines.append(
            f"    {name}: {{area_m2_midpoint: {r['area_m2_midpoint']:g}, target_pct: {tgt}, min_pct: {r['min_pct']}, "
            f"median_pct: {r['median_pct']}, max_pct: {r['max_pct']}, frac_in_band: {r['frac_in_band']}, "
            f"median_in_band: {str(r['median_in_band']).lower()}}}"
        )
    return "\n".join(lines) + "\n"


def calibrate(config_path: str, write: bool = True) -> dict:
    """Measure realised leak % of mean demand per bucket; optionally record it in the YAML (ranges untouched)."""
    cfg = load_config(config_path)
    results = measure(cfg)
    if write:
        p = Path(config_path)
        text = p.read_text()
        new, n = re.subn(r"(?ms)^calibration:.*?(?=^fault_locations:)", lambda _: _yaml_block(results), text)
        if n != 1:
            raise RuntimeError("could not locate the calibration block in " + config_path)
        new = new.replace(
            "leak_area_m2:      # PROVISIONAL — calibrate in G2 (module 02 §6 step 3)",
            "leak_area_m2:      # checked by calibration below (G2); unchanged unless a bucket median is out of band",
        )
        p.write_text(new)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sim.generate.calibrate")
    ap.add_argument("--config", default="config/generation/ds1.yaml")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    res = calibrate(a.config, write=not a.no_write)
    for k, r in res.items():
        print(f"{k:12s} area {r['area_m2_midpoint']:.3g}  min/med/max % = {r['min_pct']}/{r['median_pct']}/{r['max_pct']}  "
              f"in-band {r['frac_in_band']:.0%}  median_in_band={r['median_in_band']}")  # fmt: skip
    return 0 if all(r["median_in_band"] for r in res.values()) else 3


if __name__ == "__main__":
    sys.exit(main())
