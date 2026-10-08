"""Identifier builders and validators (BACKBONE §5.1; extra formats per BACKBONE_ISSUES BI-15).

Every ID in the system is built here so that formats cannot drift between modules.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

SIMULATION_ID_RE = re.compile(r"^sim_ds\d+_\d{6}$")
SESSION_ID_RE = re.compile(r"^sess_[0-9a-f]{6}$")
MODEL_VERSION_RE = re.compile(r"^[a-z0-9]+_ds\d+_\d{12}$")
INCIDENT_ID_RE = re.compile(r"^inc_[0-9a-f]{6}_\d+$")
LEAK_NODE_RE = re.compile(r"^LK_.+$")
SPLIT_HALF_SUFFIX = "_B"


def _stamp(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H%M")


def network_id(slug: str, n: int) -> str:
    return f"net_{slug}_v{n}"


def simulation_id(dataset_version: str, index: int) -> str:
    """`sim_<datasetVersion>_<6-digit index>` e.g. ``sim_ds1_000417``."""
    return f"sim_{dataset_version}_{index:06d}"


def new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:6]}"


def session_short(session_id: str) -> str:
    return session_id.removeprefix("sess_")


def incident_id(session_id: str, sim_time_s: int) -> str:
    """`inc_<sessionShort>_<simTimeS>` — matches the §7.12 example ``inc_3f9a1c_43200``."""
    return f"inc_{session_short(session_id)}_{sim_time_s}"


def challenge_id(session_id: str, sim_time_s: int) -> str:
    """BI-15 proposal: `chl_<sessionShort>_<simTimeS>`."""
    return f"chl_{session_short(session_id)}_{sim_time_s}"


def model_version(arch: str, dataset_version: str, now: datetime | None = None) -> str:
    """`<arch>_<dsVersion>_<yyyymmddhhmm>` e.g. ``mlp_ds1_202610091830``."""
    return f"{arch}_{dataset_version}_{_stamp(now)}"


def thresholds_version(dataset_version: str, now: datetime | None = None) -> str:
    return f"thr_{dataset_version}_{_stamp(now)}"


def signatures_version(dataset_version: str, now: datetime | None = None) -> str:
    return f"sig_{dataset_version}_{_stamp(now)}"


def leak_node_id(pipe_id: str) -> str:
    """Hidden leak node for a split pipe. NEVER exposed outside reveal (§5.1, §11)."""
    return f"LK_{pipe_id}"


def split_half_id(pipe_id: str) -> str:
    return f"{pipe_id}{SPLIT_HALF_SUFFIX}"


def canonical_link_id(link_id: str) -> str:
    """Map split-pipe halves back to the canonical pipe id: ``4_B`` → ``4`` (§5.1)."""
    return link_id.removesuffix(SPLIT_HALF_SUFFIX)


def is_hidden_element(element_id: str) -> bool:
    return bool(LEAK_NODE_RE.match(element_id))
