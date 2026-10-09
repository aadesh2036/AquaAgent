"""AI monitor: listens to every simulated step, runs predictor → residuals → detector → localisation.

Firewall (BACKBONE §11): the only thing taken from a HydraulicSnapshot is what ``SensorWindowBuffer`` extracts
(sensor + SCADA context values with sensor noise). Everything this module returns is derived from that.

Models (owner decision 2026-10-09, P-05-2): generalised GNN predictor + SensorSetNet detector + physics
signature matcher built from the network map. Paths from env (BACKBONE §10.4):
AQUA_PREDICTOR_ARTIFACT | AQUA_PREDICTOR_URL, AQUA_THRESHOLDS_URI + AQUA_SIGNATURES_URI | AQUA_DETECTOR_URL.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

from api.clients.predictor_client import PredictorClient
from api.pipeline.window_buffer import SensorWindowBuffer
from shared import units
from shared.contracts.models import (
    AnomalyResult,
    AnomalyStatus,
    HydraulicSnapshot,
    NetworkStatus,
    NetworkTopology,
    SensorLayout,
)

log = logging.getLogger("aquaagent.api.monitor")
SENSORS = ("S1", "S2", "S3", "F1", "F2")
HISTORY = 96  # 8 h of score history for the sparkline
AI_LABEL = "BY AI"


class AIMonitor:
    def __init__(self, settings, topology: NetworkTopology, layout: SensorLayout) -> None:
        self.topology, self.layout = topology, layout
        self.enabled, self.error = False, None
        self.predictor = self.detector = self.matcher = None
        try:
            from api.clients.detector_client import make_detector_and_localiser

            self.predictor = PredictorClient(artifact=settings.predictor_artifact)
            self.detector, self.matcher = make_detector_and_localiser(
                settings.thresholds_uri, settings.signatures_uri
            )
            self.enabled = True
        except Exception as exc:  # the simulator must keep working without the AI
            self.error = f"AI disabled: {exc}"
            log.warning(self.error)
        self.sensor_node = {s.sensor_id: s.node_id for s in layout.pressure}
        self.sensor_link = {f.sensor_id: f.link_id for f in layout.flow}
        self.zone_of_node = {n.node_id: n.zone_id for n in topology.nodes}
        self.zone_of_link = {lk.link_id: lk.zone_id for lk in topology.links}
        self.links_of_node = {}
        for lk in topology.links:
            for n in (lk.start_node, lk.end_node):
                self.links_of_node.setdefault(n, []).append(lk.link_id)
        self.reset(0, network_id=topology.network_id)

    # ------------------------------------------------------------------ lifecycle
    def reset(self, seed: int, network_id: str | None = None) -> None:
        self.buffer = SensorWindowBuffer(
            self.layout, network_id or self.topology.network_id, seed=seed + 7919
        )
        if self.detector:
            self.detector.reset()
        self.response = self.frame = None
        self.result: AnomalyResult | None = None
        self.z_hist: deque = deque(maxlen=24)
        self.score_hist: deque = deque(maxlen=HISTORY)
        self.notifications: list[dict] = []
        self.highlight: dict | None = None
        self.last_time_s: int | None = None

    def acknowledge(self) -> None:
        """Operator clears the alarm: detector unlatches; history and notifications are kept."""
        if self.detector:
            self.detector.reset()
        self.result, self.highlight = None, None
        self.z_hist.clear()

    # ------------------------------------------------------------------ per step
    def observe(self, snapshots: list[HydraulicSnapshot]) -> None:
        if not self.enabled:
            return
        from ml.anomaly.frames import residual_frame

        for snap in snapshots:
            self.buffer.push(snap)
            w = self.buffer.window()
            if w is None or w.window[-1].sim_time_s == self.last_time_s:
                continue
            self.last_time_s = w.window[-1].sim_time_s
            try:
                self.response = self.predictor.predict(w)
                self.frame = residual_frame(w, self.response, self.detector.cfg["sigmas"])
                prev = self.result.status if self.result else AnomalyStatus.NORMAL
                self.result = self.detector.update(self.frame, w.window[-1].context)
            except Exception as exc:
                self.error = f"AI step failed: {exc}"
                log.exception("AI step failed")
                continue
            self.z_hist.append([self.frame.z.get(s, 0.0) for s in SENSORS])
            self.score_hist.append([self.last_time_s, self.result.anomaly_score, self.result.status.value])
            if self.result.status == AnomalyStatus.ANOMALY and prev != AnomalyStatus.ANOMALY:
                self._on_anomaly()
            elif prev == AnomalyStatus.ANOMALY and self.result.status != AnomalyStatus.ANOMALY:
                self._on_recovered("readings back to normal for 30 min")

    def _on_anomaly(self) -> None:
        r = self.result
        start = r.first_flag_time_s or self.last_time_s
        n_steps = max(1, min(len(self.z_hist), (self.last_time_s - start) // 300 + 1))
        z_mean = np.mean(np.array(self.z_hist)[-n_steps:], axis=0)
        loc = self.matcher.rank(z_mean, top_k=3) if self.matcher else None
        self.highlight = self._highlight(loc, r)
        where = (
            f"probable zone {loc.probable_zone.zone_id}; most likely "
            + ", ".join(f"{c.location_kind} {c.location_id}" for c in loc.candidates)
            if loc
            else "sensors " + ", ".join(r.driving_sensors)
        )
        self.notifications.append(
            {
                "id": f"ai_{self.last_time_s}",
                "sim_time_s": self.last_time_s,
                "clock": units.clock_label(self.last_time_s),
                "status": r.status.value,
                "anomaly_score": r.anomaly_score,
                "driving_sensors": r.driving_sensors,
                "text": f"AI detected an anomaly at {units.clock_label(self.last_time_s)} — {where}.",
                "probable_zone": loc.probable_zone.zone_id if loc else None,
            }
        )

    def _on_recovered(self, why: str) -> None:
        self.highlight = None
        self.notifications.append(
            {
                "id": f"ai_ok_{self.last_time_s}",
                "sim_time_s": self.last_time_s,
                "clock": units.clock_label(self.last_time_s or 0),
                "status": "NORMAL",
                "anomaly_score": self.result.anomaly_score if self.result else 0.0,
                "driving_sensors": [],
                "text": f"AI cleared the alarm at {units.clock_label(self.last_time_s or 0)} — {why}.",
                "probable_zone": None,
            }
        )

    def operator_repair(self) -> None:
        """Operator repaired/reset a pipe (public user action): re-arm the AI with a fresh history.

        If the problem is still there, the detector alarms again after T steps of new evidence."""
        was = self.result is not None and self.result.status == AnomalyStatus.ANOMALY
        self.acknowledge()
        if was:
            self._on_recovered("operator reported a repair; AI re-armed and listening")

    def _highlight(self, loc, r: AnomalyResult) -> dict:
        """Elements to paint: candidate pipes/junctions (+ probable zone). Label is always 'BY AI'."""
        cands = []
        if loc:
            for c in loc.candidates:
                kind = c.location_kind.value if hasattr(c.location_kind, "value") else c.location_kind
                if kind == "pipe":
                    lk = next(lk for lk in self.topology.links if lk.link_id == c.location_id)
                    nodes, links = [lk.start_node, lk.end_node], [c.location_id]
                else:
                    nodes, links = [c.location_id], []
                cands.append(
                    {
                        "rank": c.rank,
                        "location_kind": kind,
                        "location_id": c.location_id,
                        "zone_id": c.zone_id,
                        "score": c.score,
                        "similarity": c.similarity,
                        "nodes": nodes,
                        "links": links,
                    }
                )
            zone = loc.probable_zone.zone_id
            zone_score = loc.probable_zone.score
        else:  # fallback: zones of the driving sensors
            zones = [
                self.zone_of_node.get(self.sensor_node.get(s))
                or self.zone_of_link.get(self.sensor_link.get(s))
                for s in r.driving_sensors
            ]
            zone, zone_score = (zones[0] if zones else None), None
        return {
            "label": AI_LABEL,
            "method": loc.method if loc else "driving_sensor_zone",
            "signatures_version": loc.signatures_version if loc else None,
            "probable_zone": zone,
            "zone_score": zone_score,
            "zone_nodes": [n for n, z in self.zone_of_node.items() if z == zone],
            "zone_links": [lk for lk, z in self.zone_of_link.items() if z == zone],
            "candidates": cands,
            "detected_at_s": self.last_time_s,
        }

    # ------------------------------------------------------------------ views
    @property
    def network_status(self) -> NetworkStatus:
        if not self.result:
            return NetworkStatus.NORMAL
        return {AnomalyStatus.ANOMALY: NetworkStatus.ANOMALY, AnomalyStatus.WATCH: NetworkStatus.WATCH}.get(
            self.result.status, NetworkStatus.NORMAL
        )

    def state(self) -> dict:
        out: dict = {
            "enabled": self.enabled,
            "error": self.error,
            "label": AI_LABEL,
            "models": {
                "predictor": getattr(self.predictor, "model_version", None),
                "predictor_arch": getattr(self.predictor, "arch", None),
                "detector": self.detector.version if self.detector else None,
                "detector_kind": self.detector.cfg.get("detector") if self.detector else None,
                "signatures": self.matcher.version if self.matcher else None,
            },
            "sim_time_s": self.last_time_s,
            "steps_observed": len(self.score_hist),
            "status": self.result.status.value if self.result else "NORMAL",
            "anomaly_score": self.result.anomaly_score if self.result else 0.0,
            "driving_sensors": self.result.driving_sensors if self.result else [],
            "first_flag_time_s": self.result.first_flag_time_s if self.result else None,
            "confirmed_time_s": self.result.confirmed_time_s if self.result else None,
            "nodes": {},
            "flows": {},
            "score_history": list(self.score_hist),
            "notifications": self.notifications[-10:],
            "highlight": self.highlight,
        }
        if self.response is None:
            return out
        rec = self.response.reconstruct.pressure_m if self.response.reconstruct else {}
        sensor_at = {n: s for s, n in self.sensor_node.items()}
        for node, p in rec.items():
            sid = sensor_at.get(node)
            e = {"ai_pressure_m": p, "kind": "sensor" if sid else "estimated", "sensor_id": sid}
            if sid and self.response.leave_one_out and sid in self.response.leave_one_out:
                loo = self.response.leave_one_out[sid]
                e |= {
                    "observed_m": loo.observed_m,
                    "ai_without_sensor_m": loo.predicted_m,
                    "residual_m": self.frame.residuals.get(sid) if self.frame else None,
                    "z": self.frame.z.get(sid) if self.frame else None,
                }
            out["nodes"][node] = e
        for fid, loo in (self.response.leave_one_out_flow or {}).items():
            out["flows"][fid] = {
                "link_id": self.sensor_link.get(fid),
                "observed_lps": loo.observed_lps,
                "ai_without_sensor_lps": loo.predicted_lps,
                "residual_lps": self.frame.residuals.get(fid) if self.frame else None,
                "z": self.frame.z.get(fid) if self.frame else None,
            }
        return out
