"""Step 2 tests: NetworkConfig export / load and .inp round-trip."""

from __future__ import annotations

import json

import wntr

import sim.engine.network as net
from shared.contracts.models import NetworkConfig

JUNC = ["2", "3", "4", "5", "6", "7"]


def _pressures(wn):
    return wntr.sim.WNTRSimulator(wn).run_sim().node["pressure"][JUNC]


def test_json_matches_constants():
    path = net.DEFAULT_CONFIG_DIR / f"{net.NETWORK_ID}.json"
    cfg = NetworkConfig.model_validate(json.loads(path.read_text()))
    assert cfg == net.network_config()
    assert len(cfg.nodes) == 8 and len(cfg.links) == 9
    assert net.load_network_config() == cfg
    assert net.load_network_config(path) == cfg


def test_link_endpoints():
    cfg = net.load_network_config()
    ends = {link.link_id: (link.start_node, link.end_node) for link in cfg.links}
    for p, (s, e, _, _) in net.PIPES.items():
        assert ends[p] == (s, e)
    assert ends["9"] == ("1", "2")
    assert [t.node_id for t in cfg.taps] == ["3", "4", "6"]
    assert cfg.valves[0].link_id == "7"


def test_export_to_tmp_and_inp_roundtrip(tmp_path):
    cfg = net.export_network_config(tmp_path)
    assert net.load_network_config(tmp_path / f"{cfg.network_id}.json") == cfg
    inp = tmp_path / f"{cfg.network_id}.inp"
    wn = wntr.network.WaterNetworkModel(str(inp))
    wn.options.hydraulic.demand_model = "PDD"
    # .inp stores values at limited decimal precision (SI -> text), so ~1e-5 m drift, not exact
    assert wn.num_pipes == 8 and wn.num_nodes == 8 and wn.num_pumps == 1
    ref = _pressures(net.build_network(pipe_split_pos=None))
    assert (ref - _pressures(wn)).abs().max().max() <= 1e-4


def test_committed_inp_roundtrip():
    inp = net.DEFAULT_CONFIG_DIR / f"{net.NETWORK_ID}.inp"
    wn = wntr.network.WaterNetworkModel(str(inp))
    ref = _pressures(net.build_network(pipe_split_pos=None))
    assert (ref - _pressures(wn)).abs().max().max() <= 1e-4
