"""Edge-aware GATv2 predictor with residual connections (BACKBONE §9.1 rung 3).

Pure PyTorch (no torch_geometric) so the same artifact runs in the api container, the SageMaker
training container and the endpoint without extra wheels. Works on any ``edge_index`` — nothing here
is specific to the 8-node network; node identity is never an input (only physical attributes,
observations and the placement mask).

Layer (per head):  a_ij = softmax_j( att · LeakyReLU(W_s h_j + W_t h_i + W_e e_ij) ),
                   h_i ← LN(h_i + W_o Σ_j a_ij (W_s h_j + W_e e_ij)),  h_i ← LN(h_i + FFN(h_i)).
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional

from ml.features.tensorize import N_EDGE_FEATURES, N_NODE_FEATURES, GraphStatic


def scatter_softmax(logits: torch.Tensor, index: torch.Tensor, n: int) -> torch.Tensor:
    """Softmax of ``logits [E, H]`` over edges sharing the same target ``index [E]``."""
    h = logits.shape[1]
    idx = index.unsqueeze(1).expand(-1, h)
    mx = torch.full((n, h), float("-inf"), dtype=logits.dtype, device=logits.device)
    mx = mx.scatter_reduce(0, idx, logits, reduce="amax", include_self=True)
    ex = (logits - mx[index]).exp()
    den = torch.zeros((n, h), dtype=logits.dtype, device=logits.device).index_add_(0, index, ex)
    return ex / den[index].clamp_min(1e-16)


class EdgeGATv2Layer(nn.Module):
    def __init__(self, dim: int, heads: int, dropout: float) -> None:
        super().__init__()
        assert dim % heads == 0
        self.h, self.dh = heads, dim // heads
        self.w_src = nn.Linear(dim, dim)
        self.w_dst = nn.Linear(dim, dim)
        self.w_edge = nn.Linear(dim, dim, bias=False)
        self.att = nn.Parameter(torch.empty(heads, self.dh))
        nn.init.xavier_uniform_(self.att)
        self.out = nn.Linear(dim, dim)
        self.norm1 = nn.LayerNorm(dim)
        self.ffn = nn.Sequential(nn.Linear(dim, 2 * dim), nn.GELU(), nn.Linear(2 * dim, dim))
        self.norm2 = nn.LayerNorm(dim)
        self.drop = nn.Dropout(dropout)
        self.last_attention: torch.Tensor | None = None

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor, e: torch.Tensor) -> torch.Tensor:
        src, dst = edge_index
        n = h.shape[0]
        xs = self.w_src(h)[src]
        xe = self.w_edge(e)
        m = (xs + self.w_dst(h)[dst] + xe).view(-1, self.h, self.dh)
        logits = (functional.leaky_relu(m, 0.2) * self.att).sum(-1)  # [E, H]
        alpha = scatter_softmax(logits, dst, n)
        self.last_attention = alpha.detach()
        msg = (xs + xe).view(-1, self.h, self.dh) * self.drop(alpha).unsqueeze(-1)
        agg = torch.zeros(n, self.h, self.dh, dtype=h.dtype, device=h.device).index_add_(0, dst, msg)
        h = self.norm1(h + self.drop(self.out(agg.reshape(n, -1))))
        return self.norm2(h + self.drop(self.ffn(h)))


class GNNPredictor(nn.Module):
    """Node encoder + edge encoder → L × EdgeGATv2 (residual) → head decoder (+ flow-link decoder)."""

    def __init__(
        self,
        n_node_features: int = N_NODE_FEATURES,
        n_edge_features: int = N_EDGE_FEATURES,
        hidden: int = 64,
        layers: int = 4,
        heads: int = 4,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.node_enc = nn.Sequential(
            nn.Linear(n_node_features, hidden), nn.GELU(), nn.Linear(hidden, hidden)
        )
        self.edge_enc = nn.Sequential(
            nn.Linear(n_edge_features, hidden), nn.GELU(), nn.Linear(hidden, hidden)
        )
        self.layers = nn.ModuleList(EdgeGATv2Layer(hidden, heads, dropout) for _ in range(layers))
        self.head_dec = nn.Sequential(nn.Linear(hidden, hidden), nn.GELU(), nn.Linear(hidden, 1))
        self.flow_dec = nn.Sequential(nn.Linear(3 * hidden, hidden), nn.GELU(), nn.Linear(hidden, 1))
        self._ei_cache: dict[tuple[int, int], torch.Tensor] = {}

    def _batched_edge_index(self, gs: GraphStatic, b: int, device) -> torch.Tensor:
        key = (b, id(gs))
        if key not in self._ei_cache:
            off = (torch.arange(b) * gs.n_nodes).repeat_interleave(gs.edge_index.shape[1])
            self._ei_cache = {key: (gs.edge_index.repeat(1, b) + off).to(device)}
        return self._ei_cache[key]

    def forward(self, x: torch.Tensor, e: torch.Tensor, gs: GraphStatic) -> tuple[torch.Tensor, torch.Tensor]:
        b, n, _ = x.shape
        h = self.node_enc(x).reshape(b * n, -1)
        he = self.edge_enc(e).reshape(b * e.shape[1], -1)
        ei = self._batched_edge_index(gs, b, x.device)
        for layer in self.layers:
            h = layer(h, ei, he)
        head_z = self.head_dec(h).view(b, n)
        hn = h.view(b, n, -1)
        s, t = gs.edge_index[:, gs.flow_edge_fwd]
        he_f = he.view(b, e.shape[1], -1)[:, gs.flow_edge_fwd]
        flow_z = self.flow_dec(torch.cat([hn[:, s], hn[:, t], he_f], dim=-1)).squeeze(-1)
        return head_z, flow_z
