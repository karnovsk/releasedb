import { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AgGridReact } from 'ag-grid-react';
import { themeQuartz, colorSchemeDark } from 'ag-grid-community';
import type { ColDef, GridReadyEvent, RowClickedEvent } from 'ag-grid-community';

const darkTheme = themeQuartz.withPart(colorSchemeDark);
import { apiGet } from '../api/client';
import type { PagedReleases, Project, Release } from '../types';
import StatusBadge from '../components/StatusBadge';

const PAGE_SIZE = 25;

// AG Grid cell renderer for the status column.
function StatusCellRenderer({ value }: { value: string }) {
  return <StatusBadge status={value} />;
}

export default function ReleasesPage() {
  const navigate = useNavigate();
  const [quickFilter, setQuickFilter] = useState('');

  // Fetch up to 500 releases; AG Grid handles client-side sort/filter/pagination.
  const { data, isLoading, error } = useQuery<PagedReleases>({
    queryKey: ['releases'],
    queryFn: () => apiGet<PagedReleases>('/api/releases?limit=500&offset=0'),
  });

  const { data: projects } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: () => apiGet<Project[]>('/api/projects'),
  });

  const projectMap = useMemo(() => {
    const m = new Map<string, string>();
    projects?.forEach((p) => m.set(p.id, p.name));
    return m;
  }, [projects]);

  const colDefs = useMemo<ColDef<Release>[]>(() => [
    {
      field: 'release_name',
      headerName: 'Release',
      flex: 2,
      minWidth: 180,
      sortable: true,
      filter: true,
    },
    {
      headerName: 'Project',
      flex: 1,
      minWidth: 120,
      sortable: true,
      filter: true,
      valueGetter: ({ data }) => (data?.project_id ? projectMap.get(data.project_id) ?? '' : ''),
    },
    {
      field: 'version',
      flex: 1,
      minWidth: 100,
      sortable: true,
      filter: true,
    },
    {
      field: 'status',
      flex: 1,
      minWidth: 120,
      sortable: true,
      filter: true,
      cellRenderer: StatusCellRenderer,
    },
    {
      field: 'created_by',
      headerName: 'Created by',
      flex: 1,
      minWidth: 120,
      sortable: true,
      filter: true,
    },
    {
      field: 'created_at',
      headerName: 'Created',
      flex: 1,
      minWidth: 140,
      sortable: true,
      valueFormatter: ({ value }) =>
        value ? new Date(value as string).toLocaleString() : '',
    },
    {
      field: 'target_date',
      headerName: 'Target date',
      flex: 1,
      minWidth: 120,
      sortable: true,
      hide: true,
    },
    {
      field: 'updated_at',
      headerName: 'Updated',
      flex: 1,
      minWidth: 140,
      sortable: true,
      hide: true,
      valueFormatter: ({ value }) =>
        value ? new Date(value as string).toLocaleString() : '',
    },
    {
      field: 'notes',
      flex: 2,
      minWidth: 200,
      hide: true,
    },
  ], [projectMap]);

  const defaultColDef = useMemo<ColDef>(() => ({
    resizable: true,
    suppressMovable: false,
  }), []);

  const onRowClicked = useCallback(
    (e: RowClickedEvent<Release>) => {
      if (e.data) navigate(`/releases/${e.data.id}`);
    },
    [navigate]
  );

  const onGridReady = useCallback((_e: GridReadyEvent) => {}, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        Loading releases…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        Failed to load releases: {(error as Error).message}
      </div>
    );
  }

  const releases = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {/* Filter bar */}
      <div className="flex items-center gap-4 shrink-0">
        <input
          type="text"
          placeholder="Search releases…"
          value={quickFilter}
          onChange={(e) => setQuickFilter(e.target.value)}
          className="
            bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100
            placeholder-gray-500 focus:outline-none focus:border-blue-500 w-72
          "
        />
        <span className="text-sm text-gray-500">
          {total} release{total !== 1 ? 's' : ''}
        </span>
        <span className="text-xs text-gray-600 ml-auto">
          Click a row to view details
        </span>
      </div>

      {/* AG Grid */}
      <div className="flex-1 rounded overflow-hidden">
        <AgGridReact<Release>
          theme={darkTheme}
          rowData={releases}
          columnDefs={colDefs}
          defaultColDef={defaultColDef}
          quickFilterText={quickFilter}
          pagination
          paginationPageSize={PAGE_SIZE}
          rowSelection="single"
          onRowClicked={onRowClicked}
          onGridReady={onGridReady}
          animateRows
        />
      </div>
    </div>
  );
}
