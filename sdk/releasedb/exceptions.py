"""
releasedb.exceptions
~~~~~~~~~~~~~~~~~~~~
Exception hierarchy for the releasedb SDK.
"""

from __future__ import annotations


class ReleaseDBError(Exception):
    """Base class for all releasedb SDK errors."""


class APIError(ReleaseDBError):
    """Raised when the ReleaseDB API returns an unexpected error response."""

    def __init__(self, method: str, url: str, status_code: int, body: str) -> None:
        self.method = method
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"ReleaseDB API error: {method} {url} → {status_code}\n{body}"
        )


class NotFoundError(ReleaseDBError):
    """Raised when a requested resource does not exist (HTTP 404)."""


class ValidationError(ReleaseDBError):
    """Raised when request data fails server-side validation."""
