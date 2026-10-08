"""Build `net_epa_tutorial_v1` in WNTR and export NetworkConfig (BACKBONE §6, §7.1).

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations

from pathlib import Path

from shared.contracts.models import NetworkConfig


def build_network(network_id: str = "net_epa_tutorial_v1"):  # -> wntr.network.WaterNetworkModel
    """Build the EPA tutorial network from the official .inp (§6). Connectivity is NEVER hand-typed.

    Applies §6.3 hydraulics: WNTRSimulator, H-W, PDD (required 20 m, minimum 0 m), tank init D3.
    """
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")


def export_network_config(wn, out_json: Path, out_inp: Path) -> NetworkConfig:
    """Export `config/networks/net_epa_tutorial_v1.{json,inp}` — the topology source of truth (§6, G1)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")


def load_network_config(path: Path) -> NetworkConfig:
    """Load and validate the exported NetworkConfig (§7.1)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")
