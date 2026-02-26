from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    related_project: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    related_project: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    related_project: Optional[str] = None
    created_at: datetime
