"""SensorSetDetector: streaming == batch on real val episodes, hash check, firewall types (P-05-2)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from shared.contracts.models import AnomalyStatus, ResidualFrame, WindowContext

DETS = sorted(p.parent for p in Path("data/models/anomaly").glob("thr_ds1_*/detector.json"))
pytestmark = pytest.mark.skipif(
    not DETS or not Path("data/features/ds1/residuals").exists(),
    reason="needs a frozen detector + cached residuals",
)
SENSORS = ("S1", "S2", "S3", "F1", "F2")


@pytest.fixture(scope="module")
def det():
    from ml.anomaly.sensorset import SensorSetDetector

    return SensorSetDetector.load(str(DETS[-1]))


def test_streaming_equals_batch_on_val_episodes(det) -> None:
    from ml.anomaly.rtca import run_batch
    from ml.anomaly.select import predict_set
    from ml.anomaly.sensorset import _episodes_for

    cfg = det.cfg
    sig = np.array([cfg["sigmas"][s] for s in SENSORS])
    feat = Path("data/features/ds1")
    zz, cx, valid, lab, a = _episodes_for(
        "val", cfg["predictor_model_version"], feat, Path("data/processed/ds1"), sig
    )
    pick = [int(i) for i in np.flatnonzero(~lab.operational.to_numpy())[:3]] + [
        int(np.flatnonzero(lab.operational.to_numpy())[0])
    ]
    p = predict_set(det.model, zz[pick], cx[pick], valid[pick], cfg["history"])
    confirm, _ = run_batch(p[..., None], valid[pick], cfg["params"]["tau"], -1.0, 1, cfg["params"]["T"])
    from ml.anomaly.tune import episodes

    ctx_raw, _, _ = episodes(a, a["ctx"].astype(np.float64))
    for j, e in enumerate(pick):
        det.reset()
        got_p, got_c = [], -1
        for t in range(int(valid[e].sum())):
            frame = ResidualFrame(
                sim_time_s=300 * t,
                residuals={s: float(zz[e, t, i, 0] * sig[i]) for i, s in enumerate(SENSORS)},
                z={},
            )
            c = ctx_raw[e, t]
            res = det.update(
                frame,
                WindowContext(
                    time_of_day_s=int(c[0]),
                    tank_level_m=float(c[1]),
                    pump_status=int(c[2]),
                    pump_flow_lps=float(c[3]),
                    reservoir_head_m=float(c[4]),
                ),
            )
            if res.status == AnomalyStatus.ANOMALY and got_c < 0:
                got_c = t
                break
            got_p.append(res.anomaly_score)
        assert got_c == confirm[j]
        n = len(got_p)
        assert np.allclose(got_p, np.round(p[j, :n], 4), atol=2e-4)


def test_tampered_artifact_is_rejected(tmp_path) -> None:
    from ml.anomaly.sensorset import SensorSetDetector

    src = DETS[-1]
    for f in ("model.pt", "detector.json"):
        (tmp_path / f).write_bytes((src / f).read_bytes())
    cfg = json.loads((tmp_path / "detector.json").read_text())
    cfg["params"]["tau"] = 0.5
    (tmp_path / "detector.json").write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        SensorSetDetector.load(str(tmp_path))


def test_update_rejects_non_contract_inputs(det) -> None:
    with pytest.raises(TypeError):
        det.update({"leak_m3s": 0.01}, None)  # type: ignore[arg-type]


def test_alarm_clears_after_sustained_normal(det) -> None:
    from shared.contracts.models import AnomalyStatus as S

    det.reset()
    seq = iter([0.999] * det.t + [0.1] * det.clear_after + [0.1])
    real = det.score
    det.score = lambda: (next(seq), {"F2": 1.0})  # type: ignore[method-assign]
    ctx = WindowContext(
        time_of_day_s=0, tank_level_m=2.0, pump_status=1, pump_flow_lps=40.0, reservoir_head_m=213.36
    )
    try:
        out = [
            det.update(ResidualFrame(sim_time_s=300 * i, residuals={"F2": 0.0}, z={}), ctx).status
            for i in range(det.t + det.clear_after)
        ]
    finally:
        det.score = real  # type: ignore[method-assign]
        det.reset()
    assert out[det.t - 1] == S.ANOMALY
    assert all(s == S.ANOMALY for s in out[det.t - 1 : -1]) and out[-1] == S.NORMAL
