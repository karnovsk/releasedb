import { useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import type { Node, Edge, NodeTypes, OnNodeClick } from '@xyflow/react';
import Dagre from '@dagrejs/dagre';
import { apiGet } from '../api/client';
import type { LineageResponse } from '../types';
import StatusBadge from '../components/StatusBadge';

// ---------------------------------------------------------------------------
// Custom node component
// ---------------------------------------------------------------------------

interface ReleaseNodeData {
  release_name: string;
  version: string;
  status: string;
  isCurrent: boolean;
  [key: string]: unknown;
}

function ReleaseNode({ data }: { data: ReleaseNodeData }) {
  const border = data.isCurrent
    ? 'border-blue-500 bg-blue-950/60'
    : 'border-gray-600 bg-gray-800/80';

  return (
    <div className={`rounded border px-3 py-2 text-sm min-w-[160px] cursor-pointer ${border}`}>
      <div className="font-semibold text-gray-100 truncate">{data.release_name}</div>
      <div className="flex items-center gap-1.5 mt-1">
        <span className="text-gray-400 text-xs">{data.version}</span>
        <StatusBadge status={data.status} />
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = { release: ReleaseNode };

// ---------------------------------------------------------------------------
// Dagre layout helper
// ---------------------------------------------------------------------------

const NODE_W = 180;
const NODE_H = 70;

function applyDagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new Dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 50 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));

  // API edge: from_release_id = child, to_release_id = parent (ancestor).
  // For TB layout we want ancestors at the top, so dagre edge goes parent → child.
  // Each React Flow edge has source = ancestor, target = child (set below).
  // Here we mirror that: g.setEdge(ancestor, child).
  edges.forEach((e) => g.setEdge(e.source, e.target));

  Dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } };
  });
}

// ---------------------------------------------------------------------------
// Inner graph component (needs ReactFlowProvider in scope)
// ---------------------------------------------------------------------------

function LineageGraph({ releaseId }: { releaseId: string }) {
  const navigate = useNavigate();
  const { fitView } = useReactFlow();

  const { data, isLoading, error } = useQuery<LineageResponse>({
    queryKey: ['lineage', releaseId],
    queryFn: () => apiGet<LineageResponse>(`/api/releases/${releaseId}/lineage?direction=both`),
  });

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Rebuild the graph whenever data changes.
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

    // API edge: from_release_id = child (depends on), to_release_id = ancestor.
    // We draw the arrow FROM ancestor TO child (downward in TB layout).
    const rfEdges: Edge[] = data.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.to_release_id,   // ancestor
      target: e.from_release_id, // child / dependent
      style: { stroke: '#4b5563' },
    }));

    const laid = applyDagreLayout(rfNodes, rfEdges);
    setNodes(laid);
    setEdges(rfEdges);

    // Fit after layout — small timeout lets React Flow measure node sizes first.
    setTimeout(() => fitView({ padding: 0.2 }), 50);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, releaseId]);

  const onNodeClick: OnNodeClick = useCallback(
    (_event, node) => {
      if (node.id !== releaseId) navigate(`/lineage/${node.id}`);
    },
    [navigate, releaseId]
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        Loading lineage…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        Failed to load lineage: {(error as Error).message}
      </div>
    );
  }

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
    >
      <Background color="#1f2937" gap={20} />
      <Controls />
    </ReactFlow>
  );
}

// ---------------------------------------------------------------------------
// Page wrapper
// ---------------------------------------------------------------------------

export default function LineagePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  if (!id) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-800 shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-gray-400 hover:text-gray-100 transition-colors"
        >
          ← Back
        </button>
        <span className="text-sm text-gray-500">
          Release lineage · click any node to navigate
        </span>
      </div>
      <div className="flex-1">
        <ReactFlowProvider>
          <LineageGraph releaseId={id} />
        </ReactFlowProvider>
      </div>
    </div>
  );
}
