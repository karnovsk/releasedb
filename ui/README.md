# ReleaseDB UI

Read-only web dashboard for ReleaseDB. Built with Vite + React + TypeScript, AG Grid, and React Flow.

## Features

### Releases table

Sortable, filterable grid showing all releases across teams. Columns include release name, project, version, status, owning team, and target date. Click any row to open the release detail view.

### Release detail

Tabbed view per release:

| Tab | Contents |
|---|---|
| **Details** | Release metadata, custom field values, project link, dependencies |
| **Artifacts** | Build outputs with file list, digests, storage URIs, and provenance |
| **Validation** | Validation run history and per-check results (status, stdout, stderr, duration) |
| **Approvals** | Sign-off records per environment (decision, approver, comment, timestamp) |
| **Deployments** | Deployment history including strategy, deployer, timing, and rollback chains |
| **Events** | Full append-only audit log with event type, actor, and payload |
| **Lineage** | Interactive DAG — all upstream and downstream release dependencies |

### Lineage graph

Interactive React Flow graph showing the selected release (highlighted) in context of its dependency chain. Click any node to navigate to that release. Zoom with scroll; pan by dragging.

### Auth

`VITE_API_TOKEN` is sent as `Authorization: Bearer <token>` on every API request. It must match the `RELEASEDB_API_TOKEN` configured on the API server.

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
