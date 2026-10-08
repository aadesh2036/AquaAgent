"""In-memory session store: one session per task (BACKBONE §3.2, §7.14.1).

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations


class SessionStore:
    def current(self):
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")
