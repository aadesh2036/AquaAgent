"""Builds SensorWindows from snapshots — the firewall boundary (BACKBONE §7.8, §11; single 300-s cadence, §5.3).

``push`` keeps only the sensor + context values of a snapshot (via ``ml.features.online.snapshot_to_step``,
with the ds1 noise model seeded per session); the snapshot itself is never stored.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from ml.features.online import snapshot_to_step
from shared.contracts.models import WINDOW_STEPS, HydraulicSnapshot, SensorLayout, SensorWindow, WindowStep


class SensorWindowBuffer:
    def __init__(self, layout: SensorLayout, network_id: str, cadence_s: int = 300, seed: int = 0) -> None:
        self.layout, self.network_id, self.cadence_s = layout, network_id, cadence_s
        self._steps: deque[WindowStep] = deque(maxlen=WINDOW_STEPS)
        self._rng = np.random.Generator(np.random.PCG64(seed))

    def push(self, snapshot: HydraulicSnapshot) -> None:
        """Extract ONLY sensor + context values (+ noise). Never keeps the snapshot."""
        if self._steps and snapshot.sim_time_s <= self._steps[-1].sim_time_s:
            return  # repeated / out-of-order snapshot (e.g. state refresh without advancing)
        self._steps.append(snapshot_to_step(snapshot, self.layout, self._rng))

    def window(self) -> SensorWindow | None:
        if not self._steps:
            return None
        return SensorWindow(
            network_id=self.network_id,
            sensor_layout_id=self.layout.sensor_layout_id,
            window=list(self._steps),
        )

    def clear(self) -> None:
        self._steps.clear()
