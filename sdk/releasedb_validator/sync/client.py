"""
releasedb_validator.sync.client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Thin HTTP client for the ReleaseDB admin API.

All methods return the parsed JSON body on success, None on 404, and raise
APIError for any other non-2xx response.  The caller (runner.py) decides what
to do with None (resource doesn't exist yet → create it).
"""

from __future__ import annotations

from typing import Any, Optional

import requests


class APIError(Exception):
    """Raised when the ReleaseDB API returns an unexpected error response."""

    def __init__(self, method: str, url: str, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"ReleaseDB API error: {method} {url} → {status_code}\n{body}"
        )


class ReleaseDBClient:
    """
    HTTP client for the ReleaseDB admin API.

    Usage::

        client = ReleaseDBClient(
            api_url="https://releasedb.internal",
            api_token="tok_...",
        )
        team = client.get_team("platform-eng")
    """

    def __init__(self, api_url: str, api_token: str, timeout: int = 30) -> None:
        self.base_url = api_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        url = f"{self.base_url}{path}"
        resp = self._session.request(method, url, timeout=self._timeout, **kwargs)

        if resp.status_code == 404:
            return None
        if resp.status_code == 204:
            return {}
        if not resp.ok:
            raise APIError(method, url, resp.status_code, resp.text)

        return resp.json()

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def get_team(self, slug: str) -> Optional[dict[str, Any]]:
        """Return team data or None if not found."""
        return self._request("GET", f"/api/teams/{slug}")

    def create_team(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/teams", json=payload)

    def update_team(self, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/api/teams/{slug}", json=payload)

    # ------------------------------------------------------------------
    # Release types
    # ------------------------------------------------------------------

    def get_release_type(self, slug: str) -> Optional[dict[str, Any]]:
        """Return release type config or None if not found."""
        return self._request("GET", f"/api/release-types/{slug}")

    def create_release_type(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/release-types", json=payload)

    def update_release_type(
        self, slug: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request("PATCH", f"/api/release-types/{slug}", json=payload)

    # ------------------------------------------------------------------
    # Field definitions
    # ------------------------------------------------------------------

    def get_field_defs(self, release_type_slug: str) -> list[dict[str, Any]]:
        """Return all field defs for a release type (empty list if none)."""
        result = self._request("GET", f"/api/release-types/{release_type_slug}/fields")
        return result if result else []

    def create_field_def(
        self, release_type_slug: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "POST", f"/api/release-types/{release_type_slug}/fields", json=payload
        )

    def update_field_def(
        self, release_type_slug: str, field_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/release-types/{release_type_slug}/fields/{field_key}",
            json=payload,
        )

    # ------------------------------------------------------------------
    # Validation definitions
    # ------------------------------------------------------------------

    def get_validation_defs(self, release_type_slug: str) -> list[dict[str, Any]]:
        """Return all validation defs for a release type (empty list if none)."""
        result = self._request(
            "GET", f"/api/release-types/{release_type_slug}/validations"
        )
        return result if result else []

    def create_validation_def(
        self, release_type_slug: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/release-types/{release_type_slug}/validations",
            json=payload,
        )

    def update_validation_def(
        self, release_type_slug: str, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/release-types/{release_type_slug}/validations/{name}",
            json=payload,
        )

    # ------------------------------------------------------------------
    # Environments (read-only from sync's perspective)
    # ------------------------------------------------------------------

    def get_environment(self, slug: str) -> Optional[dict[str, Any]]:
        """Return environment or None if not found. Used to validate env references."""
        return self._request("GET", f"/api/environments/{slug}")
