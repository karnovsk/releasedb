import React, { useCallback, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import type { Node, Edge, NodeTypes } from '@xyflow/react';
import Dagre from '@dagrejs/dagre';
import { apiGet } from '../api/client';
import type { Release, LineageResponse, ReleaseEvent, Project } from '../types';
import StatusBadge from '../components/StatusBadge';

// ---------------------------------------------------------------------------
// Custom node (same as before, handles on Left/Right for LR layout)
// ---------------------------------------------------------------------------

interface ReleaseNodeData {
  release_name: string;
  version: string;
  status: string;
  isCurrent: boolean;
  [key: string]: unknown;
}

const STATUS_NODE_CLS: Record<string, string> = {
  draft:      'border-gray-500  bg-gray-800/80',
  validating: 'border-yellow-500 bg-yellow-950/60',
  approved:   'border-blue-400  bg-blue-950/60',
  deploying:  'border-orange-400 bg-orange-950/60',
  deployed:   'border-green-500  bg-green-950/60',
  failed:     'border-red-500   bg-red-950/60',
  cancelled:  'border-gray-600  bg-gray-900/60',
  archived:   'border-purple-500 bg-purple-950/60',
};

const HANDLE_STYLE: React.CSSProperties = {
  width: 8,
  height: 8,
  background: '#4b5563',
  border: '1px solid #6b7280',
};

function ReleaseNode({ data }: { data: ReleaseNodeData }) {
  const statusCls = STATUS_NODE_CLS[data.status] ?? 'border-gray-600 bg-gray-800/80';
  const currentRing = data.isCurrent ? 'ring-2 ring-white ring-offset-1 ring-offset-gray-900' : '';

  return (
    <>
      <Handle type="target" position={Position.Left} style={HANDLE_STYLE} />
      <div className={`rounded border px-3 py-2 text-sm min-w-[160px] cursor-pointer ${statusCls} ${currentRing}`}>
        <div className="font-semibold text-gray-100 truncate">{data.release_name}</div>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="text-gray-400 text-xs">{data.version}</span>
          <StatusBadge status={data.status} />
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={HANDLE_STYLE} />
    </>
  );
}

const nodeTypes: NodeTypes = { release: ReleaseNode };

// ---------------------------------------------------------------------------
// Dagre layout
// ---------------------------------------------------------------------------

const NODE_W = 180;
const NODE_H = 70;

function applyDagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new Dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', ranksep: 100, nodesep: 40 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));

  Dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } };
  });
}

// ---------------------------------------------------------------------------
// LineageGraph (inner — needs ReactFlowProvider in scope)
// ---------------------------------------------------------------------------

function LineageGraph({ releaseId }: { releaseId: string }) {
  const navigate = useNavigate();
  const { fitView } = useReactFlow();

  const { data } = useQuery<LineageResponse>({
    queryKey: ['lineage', releaseId],
    queryFn: () => apiGet<LineageResponse>(`/api/releases/${releaseId}/lineage?direction=both`),
  });

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useMemo(() => {
    if (!data) return;

    const rfNodes: Node[] = data.nodes.map((n) => ({
      id: n.id,
      type: 'release',
      position: { x: 0, y: 0 },
      data: {
        release_name: n.release_name,
        version: n.version,
        status: n.status,
        isCurrent: n.id === releaseId,
      },
    }));

    const rfEdges: Edge[] = data.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.to_release_id,
      target: e.from_release_id,
      style: { stroke: '#6b7280', strokeWidth: 1.5 },
      animated: false,
    }));

    const laid = applyDagreLayout(rfNodes, rfEdges);
    setNodes(laid);
    setEdges(rfEdges);

    setTimeout(() => fitView({ padding: 0.2 }), 50);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, releaseId]);

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (node.id !== releaseId) navigate(`/releases/${node.id}`);
    },
    [navigate, releaseId]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={onNodeClick}
      nodeTypes={nodeTypes}
      fitView
      colorMode="dark"
      style={{ background: '#030712' }}
    >
      <Background color="#374151" gap={20} />
      <Controls />
    </ReactFlow>
  );
}

// ---------------------------------------------------------------------------
// Details tab
// ---------------------------------------------------------------------------

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-gray-500 font-medium">{label}</dt>
      <dd className="text-gray-100">{children}</dd>
    </>
  );
}

function DetailsTab({ release, projectName }: { release: Release; projectName?: string }) {
  const customFields = Object.entries(release.field_values ?? {});

  return (
    <dl className="grid gap-x-6 gap-y-3 p-6 text-sm" style={{ gridTemplateColumns: '160px 1fr' }}>
      <Field label="Release name">{release.release_name}</Field>
      <Field label="Version">{release.version}</Field>
      <Field label="Status"><StatusBadge status={release.status} /></Field>
      <Field label="Created by">{release.created_by ?? '—'}</Field>
      <Field label="Created">{new Date(release.created_at).toLocaleString()}</Field>
      <Field label="Updated">{new Date(release.updated_at).toLocaleString()}</Field>
      <Field label="Target date">{release.target_date ?? '—'}</Field>
      <Field label="Notes">
        {release.notes
          ? <span className="whitespace-pre-wrap">{release.notes}</span>
          : <span className="text-gray-600">—</span>}
      </Field>
      <Field label="Project">
        {projectName
          ? <span className="text-gray-200">{projectName}</span>
          : release.project_id
            ? <span className="text-gray-500 text-xs">Loading…</span>
            : <span className="text-gray-600">—</span>}
      </Field>
      <Field label="Dependencies">
        {release.depends_on.length > 0
          ? <span className="font-mono text-xs text-gray-400">{release.depends_on.join(', ')}</span>
          : <span className="text-gray-600">None</span>}
      </Field>
      {customFields.map(([key, value]) => (
        <Field key={key} label={key}>{value ?? '—'}</Field>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------------------
// Events tab
// ---------------------------------------------------------------------------

const EVENT_DOT: Record<string, string> = {
  release_created:      'bg-gray-500',
  status_changed:       'bg-blue-400',
  deployment_triggered: 'bg-orange-400',
};

function eventDotCls(event: ReleaseEvent): string {
  if (event.event_type === 'approval_submitted') {
    return (event.payload?.decision === 'approved') ? 'bg-green-500' : 'bg-red-400';
  }
  return EVENT_DOT[event.event_type] ?? 'bg-gray-500';
}

function EventsTab({ releaseId }: { releaseId: string }) {
  const { data: events, isLoading } = useQuery<ReleaseEvent[]>({
    queryKey: ['release-events', releaseId],
    queryFn: () => apiGet<ReleaseEvent[]>(`/api/releases/${releaseId}/events`),
  });

  if (isLoading) {
    return <div className="p-6 text-gray-500 text-sm">Loading events…</div>;
  }

  if (!events || events.length === 0) {
    return <div className="p-6 text-gray-600 text-sm">No events recorded.</div>;
  }

  return (
    <ol className="p-6 flex flex-col gap-4">
      {events.map((ev) => {
        const payloadEntries = Object.entries(ev.payload ?? {}).filter(
          ([, v]) => v !== null && v !== undefined && v !== ''
        );
        return (
          <li key={ev.id} className="flex gap-3 text-sm">
            <div className="flex flex-col items-center gap-1 mt-1 shrink-0">
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${eventDotCls(ev)}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-3">
                <span className="font-medium text-gray-200">{ev.event_type}</span>
                <span className="text-xs text-gray-500">
                  {new Date(ev.occurred_at).toLocaleString()}
                </span>
              </div>
              {ev.actor_identity && (
                <div className="text-gray-500 text-xs mt-0.5">actor: {ev.actor_identity}</div>
              )}
              {payloadEntries.length > 0 && (
                <div className="mt-1 text-xs text-gray-400 flex flex-col gap-0.5">
                  {payloadEntries.map(([k, v]) => (
                    <span key={k}>
                      <span className="text-gray-500">{k}:</span>{' '}
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ReleaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<'details' | 'events'>('details');

  const { data: release } = useQuery<Release>({
    queryKey: ['release', id],
    queryFn: () => apiGet<Release>(`/api/releases/${id}`),
    enabled: !!id,
  });

  const { data: project } = useQuery({
    queryKey: ['project', release?.project_id],
    queryFn: () => apiGet<Project>(`/api/projects/${release!.project_id}`),
    enabled: !!release?.project_id,
  });

  if (!id) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-800 shrink-0">
        <button
          onClick={() => navigate('/')}
          className="text-sm text-gray-400 hover:text-gray-100 transition-colors shrink-0"
        >
          ← Back
        </button>
        <span className="font-semibold text-gray-100 truncate">
          {release?.release_name ?? '…'}
        </span>
        {release && <StatusBadge status={release.status} />}
      </div>

      {/* DAG */}
      <div className="h-72 shrink-0 border-b border-gray-800">
        <ReactFlowProvider>
          <LineageGraph releaseId={id} />
        </ReactFlowProvider>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-800 shrink-0 px-4">
        {(['details', 'events'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize border-b-2 transition-colors ${
              tab === t
                ? 'border-blue-500 text-gray-100'
                : 'border-transparent text-gray-500 hover:text-gray-300'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'details' && release && <DetailsTab release={release} projectName={project?.name} />}
        {tab === 'details' && !release && (
          <div className="p-6 text-gray-500 text-sm">Loading…</div>
        )}
        {tab === 'events' && <EventsTab releaseId={id} />}
      </div>
    </div>
  );
}
