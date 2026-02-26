# ReleaseDB UI

Read-only web interface for ReleaseDB. Two views:

- **Releases table** — sortable, filterable, configurable columns. Click a row to open its lineage.
- **Lineage graph** — visual DAG showing all ancestors and descendants of a release. Click any node to navigate.

## Prerequisites

- Node.js 18+
- ReleaseDB API running locally on port 8000

```bash
# From the project root
DATABASE_URL=postgresql://releasedb:releasedb@localhost/releasedb \
  RELEASEDB_API_TOKEN=devtoken \
  uvicorn api.main:app --reload
```

## Setup

```bash
cd ui
npm install
cp .env.local.example .env.local
# VITE_API_TOKEN must match RELEASEDB_API_TOKEN on the server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

All `/api` requests are proxied to `http://localhost:8000` by the Vite dev server,
so no CORS configuration is needed.

## Environment variables

| Variable | Description |
|---|---|
| `VITE_API_TOKEN` | Bearer token — must match `RELEASEDB_API_TOKEN` on the API server |

## Build

```bash
npm run build   # outputs to ui/dist/
```
