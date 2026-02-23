from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class TeamCreate(BaseModel):
    slug: str
    name: str
    contact_email: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class TeamResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    contact_email: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class EnvironmentCreate(BaseModel):
    slug: str
    name: str
    tier: int = 0
    requires_approval: bool = False
    config: Optional[dict[str, Any]] = None


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    tier: Optional[int] = None
    requires_approval: Optional[bool] = None
    config: Optional[dict[str, Any]] = None


class EnvironmentResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    tier: int
    requires_approval: bool
    config: Optional[dict[str, Any]] = None
