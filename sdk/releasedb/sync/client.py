"""
releasedb.sync.client
~~~~~~~~~~~~~~~~~~~~~
Re-exports ReleaseDBClient and APIError from releasedb.client for use by the
sync runner. All API methods live in the main client.
"""

from releasedb.client import ReleaseDBClient
from releasedb.exceptions import APIError

__all__ = ["ReleaseDBClient", "APIError"]
