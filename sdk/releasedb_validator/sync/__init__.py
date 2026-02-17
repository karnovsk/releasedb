"""
releasedb_validator.sync
~~~~~~~~~~~~~~~~~~~~~~~~
Config-as-code sync tool for ReleaseDB.

Parses a releasedb.yaml file and upserts teams, release type configs,
field definitions, and validation definitions via the ReleaseDB admin API.

Entry point: ``releasedb-sync`` (installed with the package)
"""

from .client import APIError, ReleaseDBClient
from .models import (
    FieldDef,
    ReleaseDBConfig,
    ReleaseTypeConfig,
    TeamConfig,
    ValidationDef,
)
from .runner import SyncResult, SyncRunner

__all__ = [
    "APIError",
    "FieldDef",
    "ReleaseDBClient",
    "ReleaseDBConfig",
    "ReleaseTypeConfig",
    "SyncResult",
    "SyncRunner",
    "TeamConfig",
    "ValidationDef",
]
