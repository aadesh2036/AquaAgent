"""HTTP client for the sim engine (BACKBONE §7.14.2). Returns shared.contracts models.

The api never imports `sim.`; tests inject a starlette TestClient wrapping the sim app.
"""

from __future__ import annotations

import httpx

from shared.contracts.models import (
    HydraulicSnapshot,
    SimAdvanceRequest,
    SimEvent,
    SimEventApplied,
    SimHealthResponse,
    SimSessionCreateRequest,
    SimSessionCreateResponse,
)


class SimUnavailable(Exception):  # noqa: N818
    """Sim engine unreachable or answered 5xx."""


class SimRejected(Exception):  # noqa: N818
    """Sim engine answered 4xx (bad event/input/unknown session)."""

    def __init__(self, detail: str, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class SimClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client if client is not None else httpx.Client(base_url=self.base_url, timeout=timeout)

    def _request(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        try:
            resp = self._client.request(method, path, json=json)
        except httpx.TransportError as exc:  # connect/read/timeout
            raise SimUnavailable(f"Simulation engine unreachable at {self.base_url}") from exc
        if resp.status_code >= 500:
            raise SimUnavailable(f"Simulation engine error {resp.status_code} at {self.base_url}")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise SimRejected(str(detail), resp.status_code)
        return resp

    def health(self) -> SimHealthResponse:
        return SimHealthResponse.model_validate(self._request("GET", "/sim/health").json())

    def create_session(self, network_id: str, seed: int, timestep_s: int = 300) -> str:
        req = SimSessionCreateRequest(network_id=network_id, seed=seed, timestep_s=timestep_s)
        resp = self._request("POST", "/sim/session", req.model_dump(mode="json"))
        return SimSessionCreateResponse.model_validate(resp.json()).session_id

    def apply_event(self, session_id: str, event: SimEvent) -> bool:
        resp = self._request("POST", f"/sim/session/{session_id}/event", event.model_dump(mode="json"))
        return SimEventApplied.model_validate(resp.json()).applied

    def advance(self, session_id: str, steps: int) -> list[HydraulicSnapshot]:
        body = SimAdvanceRequest(steps=steps).model_dump(mode="json")
        resp = self._request("POST", f"/sim/session/{session_id}/advance", body)
        return [HydraulicSnapshot.model_validate(s) for s in resp.json()]

    def snapshot(self, session_id: str) -> HydraulicSnapshot:
        resp = self._request("GET", f"/sim/session/{session_id}/snapshot")
        return HydraulicSnapshot.model_validate(resp.json())

    def reset(self, session_id: str) -> HydraulicSnapshot:
        resp = self._request("POST", f"/sim/session/{session_id}/reset")
        return HydraulicSnapshot.model_validate(resp.json())
