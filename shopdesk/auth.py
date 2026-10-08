"""Google credentials for the two kinds of calls our agents make.

* Agent -> MCP server on Cloud Run: an **identity token** (proves who is calling).
  Cloud Run checks it and the caller's `roles/run.invoker` before our code runs.
* Orchestrator -> refunds agent on Agent Runtime (A2A): an **access token**
  (OAuth, scope cloud-platform), like any Google Cloud API call.

Both work unchanged in Cloud Shell (your own identity) and on Agent Runtime
(the runtime's service identity), so the same code runs in both places.
"""

from __future__ import annotations

import base64
import json
import subprocess
import threading
import time
from urllib.parse import urlparse

import httpx
import httpx2


def _jwt_exp(token: str) -> float:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return float(json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0))


class _IdTokens:
    """Fetch and cache identity tokens per audience (they live about an hour)."""

    def __init__(self):
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def get(self, audience: str) -> str:
        with self._lock:
            tok, exp = self._cache.get(audience, ("", 0.0))
            if tok and exp - time.time() > 300:
                return tok
            tok = self._fetch(audience)
            self._cache[audience] = (tok, _jwt_exp(tok))
            return tok

    @staticmethod
    def _fetch(audience: str) -> str:
        # 1. Service identity (Agent Runtime, Cloud Run, a service-account key).
        try:
            import google.auth.transport.requests
            import google.oauth2.id_token

            return google.oauth2.id_token.fetch_id_token(
                google.auth.transport.requests.Request(), audience
            )
        except Exception:  # noqa: BLE001 - fall through to the user's identity
            pass
        # 2. A person signed in to gcloud (Cloud Shell): Cloud Run accepts this token too.
        out = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()


_ID_TOKENS = _IdTokens()


class CloudRunAuth(httpx2.Auth):
    """Adds `Authorization: Bearer <identity token>` for the target Cloud Run service."""

    def auth_flow(self, request):
        url = urlparse(str(request.url))
        audience = f"{url.scheme}://{url.netloc}"
        request.headers["Authorization"] = f"Bearer {_ID_TOKENS.get(audience)}"
        yield request


class GoogleAccessTokenAuth(httpx.Auth):
    """Adds a fresh OAuth access token (Agent Runtime A2A calls)."""

    def __init__(self):
        import google.auth

        self._creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self._lock = threading.Lock()

    def _token(self) -> str:
        from google.auth.transport.requests import Request

        with self._lock:
            if not self._creds.valid:
                self._creds.refresh(Request())
            return self._creds.token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._token()}"
        yield request
