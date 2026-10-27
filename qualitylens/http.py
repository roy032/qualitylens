"""A small HTTP client for API tests: one base URL, optional auth, a default timeout.

Methods return the raw `requests.Response` so tests can assert on status codes and bodies, including
negative cases. Set-up code wraps calls in `ok()`, which fails fast with the request and the start of
the response when set-up itself breaks, so a test failure points at the real problem.
"""
from __future__ import annotations

from typing import Any

import requests


class ApiClient:
    def __init__(self, base_url: str, auth: tuple[str, str] | None = None, token: str | None = None,
                 token_scheme: str = "Bearer", timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if auth:
            self.session.auth = auth
        if token:
            self.session.headers["Authorization"] = f"{token_scheme} {token}"

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.request(method, f"{self.base_url}{path}", **kwargs)

    def get(self, path: str, **kw) -> requests.Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> requests.Response:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw) -> requests.Response:
        return self.request("PUT", path, **kw)

    def patch(self, path: str, **kw) -> requests.Response:
        return self.request("PATCH", path, **kw)

    def delete(self, path: str, **kw) -> requests.Response:
        return self.request("DELETE", path, **kw)

    @staticmethod
    def ok(resp: requests.Response, *expected: int) -> Any:
        """Decoded JSON of a set-up call (an object or a list); fails unless the status is expected (200/201)."""
        expected = expected or (200, 201)
        assert resp.status_code in expected, (
            f"Setup call {resp.request.method} {resp.url} returned {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}
