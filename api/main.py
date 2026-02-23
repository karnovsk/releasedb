"""
ReleaseDB API
~~~~~~~~~~~~~
FastAPI application. Start with:

    uvicorn api.main:app --reload

Environment variables
---------------------
DATABASE_URL          asyncpg-compatible PostgreSQL URL
                      e.g. postgresql://user:pass@localhost/releasedb
RELEASEDB_API_TOKEN   Shared bearer token checked on every request
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.database import close_pool, init_pool
from api.routers import (
    artifacts,
    deployments,
    environments,
    release_types,
    releases,
    teams,
    validation_results,
    validation_runs,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(
    title="ReleaseDB API",
    version="1.0.0",
    description="Release management API for multi-team organisations.",
    lifespan=lifespan,
)

app.include_router(teams.router,              prefix="/api")
app.include_router(environments.router,       prefix="/api")
app.include_router(release_types.router,      prefix="/api")
app.include_router(releases.router,           prefix="/api")
app.include_router(artifacts.router,          prefix="/api")
app.include_router(validation_runs.router,    prefix="/api")
app.include_router(validation_results.router, prefix="/api")
app.include_router(deployments.router,        prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
