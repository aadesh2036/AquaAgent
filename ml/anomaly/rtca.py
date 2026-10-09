"""RTCA-style dual threshold detector (BACKBONE §9.3).

Per sensor s, at each 300-s step:
  instant_s    = |z_s| > k1
  cumulative_s = mean(|z_s| over the last W steps) > k2      (only once W steps have been seen)
  streak_s     = consecutive steps with instant_s AND cumulative_s
ANOMALY is confirmed when any streak_s ≥ T and then LATCHES until ``reset()`` (one incident per challenge).
WATCH = any instant flag (on a detecting sensor) while not confirmed. NORMAL otherwise.
Only ``detect_sensors`` (tuned on val) can raise WATCH/ANOMALY; all sensors stay in the frame as evidence.

anomaly_score = c / (c + k2), c = max_s cumulative mean|z_s|  →  0.5 exactly at the cumulative threshold.
first_flag_time_s = start of the streak that confirmed; detection_delay_steps = confirmation − that start.
driving_sensors = sensors with both flags at confirmation, by descending cumulative |z|.

``run_batch`` evaluates the same rules vectorised over many simulations (tuning/evaluation); it is checked
against the streaming class in ml/tests/test_anomaly_rtca.py.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np

from shared.contracts.models import AnomalyResult, AnomalyStatus, ResidualFrame

STEP_S = 300


class RTCADetector:
    """Instant |z|>k1; cumulative mean|z| over W > k2; ANOMALY after T consecutive both-flag steps."""

    def __init__(
        self,
        k1: float = 2.5,
        k2: float = 3.0,
        window_w: int = 6,
        consecutive_t: int = 3,
        thresholds_version: str = "",
        sensors: tuple[str, ...] = ("S1", "S2", "S3", "F1", "F2"),
        detect_sensors: tuple[str, ...] | None = None,
    ) -> None:
        self.k1, self.k2, self.w, self.t = float(k1), float(k2), int(window_w), int(consecutive_t)
        self.thresholds_version = thresholds_version
        self.sensors = sensors
        # sensors whose flags can confirm/raise status (tuned on val); others are still tracked for evidence
        self.detect = tuple(detect_sensors or sensors)
        self.sigma_table: dict = {}
        self.reset()

    def reset(self) -> None:
        self._hist = {s: deque(maxlen=self.w) for s in self.sensors}
        self._streak = {s: 0 for s in self.sensors}
        self._streak_start: dict[str, int | None] = {s: None for s in self.sensors}
        self._confirmed: AnomalyResult | None = None

    def update(self, frame: ResidualFrame) -> AnomalyResult:
        if not isinstance(frame, ResidualFrame):
            raise TypeError("RTCADetector.update takes a ResidualFrame only (§11)")
        if self._confirmed is not None:
            return self._confirmed
        t = frame.sim_time_s
        inst, cum, both = [], {}, []
        for s in self.sensors:
            z = frame.z.get(s)
            if z is None:  # missing reading: no evidence this step, streak breaks
                self._streak[s], self._streak_start[s] = 0, None
                continue
            a = abs(z)
            self._hist[s].append(a)
            c = float(np.mean(self._hist[s])) if len(self._hist[s]) == self.w else 0.0
            cum[s] = c
            i_flag, c_flag = a > self.k1, c > self.k2
            if i_flag:
                inst.append(s)
            if i_flag and c_flag and s in self.detect:
                both.append(s)
                if self._streak[s] == 0:
                    self._streak_start[s] = t
                self._streak[s] += 1
            else:
                self._streak[s], self._streak_start[s] = 0, None
        cmax = max(cum.values(), default=0.0)
        score = round(cmax / (cmax + self.k2), 4)
        frame.instant_flags = inst
        frame.cumulative_flags = [s for s, c in cum.items() if c > self.k2]
        confirming = [s for s in self.detect if self._streak[s] >= self.t]
        if confirming:
            start = min(self._streak_start[s] for s in confirming)
            self._confirmed = AnomalyResult(
                status=AnomalyStatus.ANOMALY,
                anomaly_score=score,
                first_flag_time_s=start,
                confirmed_time_s=t,
                detection_delay_steps=(t - start) // STEP_S,
                driving_sensors=sorted(both, key=lambda s: -cum[s]),
                residual_history_ref=f"session buffer last {self.w} frames",
                thresholds_version=self.thresholds_version,
            )
            return self._confirmed
        first = min((v for v in self._streak_start.values() if v is not None), default=None)
        watch = [s for s in inst if s in self.detect]
        return AnomalyResult(
            status=AnomalyStatus.WATCH if watch else AnomalyStatus.NORMAL,
            anomaly_score=score,
            first_flag_time_s=first,
            driving_sensors=sorted(inst, key=lambda s: -cum.get(s, 0.0)),
            thresholds_version=self.thresholds_version,
        )

    @classmethod
    def from_thresholds_json(cls, path: str) -> RTCADetector:
        """Load a frozen ``thresholds.json`` (local path or s3:// URI). σ lookup: ``det.sigma_table`` with
        ``ml.anomaly.residuals.sigmas_for(pump_flow_lps, det.sigma_table)``."""
        cfg = load_thresholds(path)
        p = cfg["params"]
        det = cls(
            p["k1"],
            p["k2"],
            p["W"],
            p["T"],
            cfg["thresholds_version"],
            tuple(cfg["sensors"]),
            tuple(cfg["detect_sensors"]),
        )
        det.sigma_table = cfg["sigma_table"]
        return det


def load_thresholds(path: str) -> dict:
    if str(path).startswith("s3://"):
        import boto3

        bucket, key = str(path)[5:].split("/", 1)
        body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
        return json.loads(body)
    return json.loads(Path(path).read_text())


def run_batch(
    z: np.ndarray, valid: np.ndarray, k1: float, k2: float, w: int, t: int
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised RTCA over episodes.

    z [S, L, 5] z-scores per episode/step/sensor; valid [S, L] (False = padding after episode end).
    Returns (confirm_idx [S], flag_start_idx [S]) — step index of first confirmation and the start of its
    confirming streak, −1 if never confirmed.
    """
    a = np.abs(z)
    n_s, n_l, n_c = a.shape
    cs = np.cumsum(np.concatenate([np.zeros((n_s, 1, n_c)), a], axis=1), axis=1)
    idx = np.arange(n_l)
    cum = np.zeros_like(a)
    ok = idx >= w - 1
    cum[:, ok] = (cs[:, w:][:, : ok.sum()] - cs[:, : n_l - w + 1][:, : ok.sum()]) / w
    both = (a > k1) & (cum > k2) & valid[..., None]
    streak = np.zeros((n_s, n_c), int)
    confirm = np.full(n_s, -1)
    start = np.full(n_s, -1)
    for i in range(n_l):
        streak = np.where(both[:, i], streak + 1, 0)
        hit = (streak >= t).any(1) & (confirm < 0)
        if hit.any():
            confirm[hit] = i
            # earliest start among the confirming sensors (= longest qualifying streak)
            start[hit] = i - np.where(streak[hit] >= t, streak[hit], 0).max(1) + 1
    return confirm, start
