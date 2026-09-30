"""A requests.Session stand-in keyed by (METHOD, path-after-/api/v2)."""

from __future__ import annotations

import json
from typing import Any, Callable

Handler = Callable[[dict], tuple[int, Any]] | tuple[int, Any]


class FakeResponse:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, routes: dict[tuple[str, str], Handler]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict]] = []
        self.auth = None

    def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        path = url.split("/api/v2", 1)[1]
        self.calls.append((method, path, kwargs))
        handler = self.routes.get((method, path))
        if handler is None:
            return FakeResponse(404, {"error": f"no fake route for {method} {path}"})
        status, payload = handler(kwargs) if callable(handler) else handler
        return FakeResponse(status, payload)

    def paths(self, method: str) -> list[str]:
        return [p for m, p, _ in self.calls if m == method]
