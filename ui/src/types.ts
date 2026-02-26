export interface Release {
  id: string;
  release_type_config_id: string;
  owning_team_id: string;
  release_name: string;
  version: string;
  status: string;
  target_date: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  field_values: Record<string, string>;
  depends_on: string[];
}

export interface PagedReleases {
  items: Release[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReleaseSummary {
  id: string;
  release_name: string;
  version: string;
  status: string;
}

export interface LineageEdge {
  from_release_id: string;
  to_release_id: string;
}

export interface LineageResponse {
  nodes: ReleaseSummary[];
  edges: LineageEdge[];
}
