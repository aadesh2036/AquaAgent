"""Settings from canonical env vars only (BACKBONE §10.4).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from shared.units import ft_to_m

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    mode: str = field(default_factory=lambda: os.environ.get("AQUA_MODE", "local"))
    region: str | None = field(default_factory=lambda: os.environ.get("AQUA_REGION"))
    bucket: str | None = field(default_factory=lambda: os.environ.get("AQUA_BUCKET"))
    network_id: str = field(default_factory=lambda: os.environ.get("AQUA_NETWORK_ID", "net_epa_tutorial_v1"))
    sensor_layout_id: str = field(
        default_factory=lambda: os.environ.get("AQUA_SENSOR_LAYOUT_ID", "sensors_default_v1")
    )
    sim_url: str = field(default_factory=lambda: os.environ.get("AQUA_SIM_URL", "http://localhost:8000"))
    predictor_endpoint: str | None = field(default_factory=lambda: os.environ.get("AQUA_PREDICTOR_ENDPOINT"))
    predictor_version: str | None = field(default_factory=lambda: os.environ.get("AQUA_PREDICTOR_VERSION"))
    predictor_artifact: str | None = field(default_factory=lambda: os.environ.get("AQUA_PREDICTOR_ARTIFACT"))
    thresholds_uri: str | None = field(default_factory=lambda: os.environ.get("AQUA_THRESHOLDS_URI"))
    signatures_uri: str | None = field(default_factory=lambda: os.environ.get("AQUA_SIGNATURES_URI"))
    agent: str = field(default_factory=lambda: os.environ.get("AQUA_AGENT", "template"))
    bedrock_model_id: str | None = field(default_factory=lambda: os.environ.get("AQUA_BEDROCK_MODEL_ID"))
    api_key: str | None = field(default_factory=lambda: os.environ.get("AQUA_API_KEY"))
    cors_origins: str = field(
        default_factory=lambda: os.environ.get("AQUA_CORS_ORIGINS", "http://localhost:5173")
    )
    # Tank full level for NetworkView.tank.level_pct: 20 ft (BACKBONE §6.1).
    tank_max_level_m: float = ft_to_m(20)
    config_dir: Path = field(default_factory=lambda: Path(os.environ.get("AQUA_CONFIG_DIR", _REPO_ROOT / "config")))
