"""RTCA detector: state machine, streaming == batch, residual paths, val-only tuning (module 05 §8)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ml.anomaly.residuals import SENSORS, residual_frame
from ml.anomaly.rtca import RTCADetector, run_batch
from shared.contracts.models import AnomalyStatus, ResidualFrame

FEAT = Path("data/features/ds1/val.npz")
MODELS = sorted(Path("data/models/predictor").glob("mlp_ds1_*/model.tar.gz"))


def _frames(z: np.ndarray) -> list[ResidualFrame]:
    return [
        ResidualFrame(sim_time_s=300 * i, residuals={}, z=dict(zip(SENSORS, map(float, row), strict=True)))
        for i, row in enumerate(z)
    ]


def test_single_spike_is_watch_sustained_is_anomaly_and_reset() -> None:
    det = RTCADetector(k1=2.5, k2=3.0, window_w=3, consecutive_t=2)
    z = np.zeros((20, 5))
    z[5, 1] = 9.0  # one spike
    out = [det.update(f).status for f in _frames(z)]
    assert AnomalyStatus.WATCH in out and AnomalyStatus.ANOMALY not in out
    det.reset()
    z[10:, 4] = 5.0  # sustained on F2
    res = [det.update(f) for f in _frames(z)]
    first = next(i for i, r in enumerate(res) if r.status == AnomalyStatus.ANOMALY)
    # mean|z| over W=3 is 10/3 > k2 at step 11 (both flags) → streak T=2 reached at step 12
    assert first == 12 and res[first].driving_sensors == ["F2"]
    assert all(r.status == AnomalyStatus.ANOMALY for r in res[first:])  # latched
    det.reset()
    assert det.update(_frames(np.zeros((1, 5)))[0]).status == AnomalyStatus.NORMAL


def test_non_detecting_sensor_cannot_alarm() -> None:
    det = RTCADetector(k1=2.0, k2=2.0, window_w=3, consecutive_t=2, detect_sensors=("F1", "F2"))
    z = np.zeros((30, 5))
    z[:, 1] = 10.0  # S2 screams, but S2 is not a detecting sensor
    assert all(det.update(f).status == AnomalyStatus.NORMAL for f in _frames(z))


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_streaming_equals_batch(seed) -> None:
    rng = np.random.Generator(np.random.PCG64(seed))
    z = rng.normal(size=(40, 60, 5)) * 1.3
    z[::3, 30:, 4] += rng.uniform(2, 6)  # inject sustained shifts in a third of the episodes
    valid = np.ones(z.shape[:2], bool)
    k1, k2, w, t = 2.5, 3.0, 6, 3
    confirm, start = run_batch(z, valid, k1, k2, w, t)
    for e in range(len(z)):
        det = RTCADetector(k1, k2, w, t)
        res = [det.update(f) for f in _frames(z[e])]
        idx = next((i for i, r in enumerate(res) if r.status == AnomalyStatus.ANOMALY), -1)
        assert idx == confirm[e]
        if idx >= 0:
            assert res[idx].first_flag_time_s == 300 * start[e]


@pytest.mark.skipif(not MODELS or not FEAT.exists(), reason="needs features + packaged predictor")
def test_offline_residuals_equal_online_path() -> None:
    from ml.anomaly.residuals import loo_residuals
    from ml.predictor.predict import load_artifact, predict
    from ml.tests.test_predict_parity import _window

    art = load_artifact(str(MODELS[-1]))
    with np.load(FEAT) as z:
        val = {k: z[k] for k in z.files}
    ends = [20, 77, 150, 288]
    off = loo_residuals(val, art, rows=np.array(ends))
    sig = dict.fromkeys(SENSORS, 1.0)
    for i, end in enumerate(ends):
        w = _window(val, art, range(end - 11, end + 1))
        fr = residual_frame(w, predict(w, art, "x"), sig)
        on = np.array([fr.residuals[s] for s in SENSORS])
        assert np.abs(on - off[i]).max() <= 1.01e-4  # both rounded to 4 dp like PredictorResponse


def test_tune_never_opens_test_split(monkeypatch) -> None:
    import ml.anomaly.tune as tune

    opened = []
    real = tune.load_split
    monkeypatch.setattr(tune, "load_split", lambda f, s: opened.append(s) or real(f, s))
    src = Path(tune.__file__).read_text()
    assert '"test"' not in src and "'test'" not in src
    assert all(s == "val" for s in opened)
