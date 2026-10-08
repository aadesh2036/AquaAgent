"""Session/network/sim/tap/pipe/valve routes (BACKBONE §7.14.1).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import (
    NetworkTopology,
    NetworkView,
    PipeFaultRequest,
    SessionResetRequest,
    SimStepRequest,
    TapRequest,
    ValveRequest,
)


def session_reset(body: SessionResetRequest) -> NetworkView:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def network_topology() -> NetworkTopology:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def network_state() -> NetworkView:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def sim_step(body: SimStepRequest) -> NetworkView:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def tap(body: TapRequest) -> NetworkView:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def pipe_fault(body: PipeFaultRequest) -> NetworkView:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


def valve(body: ValveRequest) -> NetworkView:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
