// Typed client for the Meridian API (proxied under /api in dev, see vite.config.ts).

export interface NetworkNode {
  id: string;
  type: "chokepoint" | "port" | "country";
  label?: string;
  lat?: number;
  lon?: number;
  baseline_daily_calls?: number;
  baseline_daily_tons?: number;
  capacity_daily_tons?: number;
}

export interface NetworkEdge {
  source: string;
  target: string;
  kind: "alt_route" | "import_share";
  added_days?: number;
  share?: number;
}

export interface Baseline {
  source: string;
  synthetic: boolean;
  data_warnings: string[];
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

export interface SourcesStatus {
  database: { reachable: boolean; error?: string };
  tables: Record<string, { rows: number; latest: string | null; distinct: number }>;
}

export interface Clamp {
  concept_id: string;
  value: number;
  from_step?: number;
  to_step?: number | null;
}

export interface ScenarioSpec {
  name?: string;
  target_chokepoint_id: string;
  capacity_reduction: number;
  duration_days: number;
  fcm_clamps?: Clamp[];
}

export interface Reroute {
  via: string;
  daily_tons: number;
  added_days: number;
}

export interface ChokepointImpact {
  chokepoint_id: string;
  capacity_multiplier: number;
  baseline_daily_tons: number;
  blocked_tons: number;
  rerouted_tons: number;
  delayed_tons: number;
  reroutes: Reroute[];
}

export interface ScenarioResult {
  scenario: ScenarioSpec;
  fcm: {
    converged: boolean;
    steps: number;
    final_activations: Record<string, number>;
    network_multipliers: Record<string, number>;
  };
  network_multipliers: Record<string, number>;
  impact: {
    rerouted_tons: number;
    delayed_tons: number;
    avg_added_days: number;
    country_exposure: Record<string, number>;
    chokepoints: ChokepointImpact[];
  };
  provisional_edges: number;
  total_edges: number;
  warnings: string[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 300)}`);
  }
  return (await res.json()) as T;
}

export function fetchBaseline(): Promise<Baseline> {
  return request<Baseline>("/network/baseline");
}

export function fetchSourcesStatus(): Promise<SourcesStatus> {
  return request<SourcesStatus>("/sources/status");
}

export interface SavedScenario {
  id: string;
  name: string;
  spec: ScenarioSpec;
  created_at: string;
  updated_at: string;
}

export function listScenarios(): Promise<SavedScenario[]> {
  return request<SavedScenario[]>("/scenarios");
}

export function saveScenario(name: string, spec: ScenarioSpec): Promise<SavedScenario> {
  return request<SavedScenario>("/scenarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, spec }),
  });
}

export function deleteScenario(id: string): Promise<void> {
  return fetch(`/api/scenarios/${id}`, { method: "DELETE" }).then(() => undefined);
}

export interface FcmConcept {
  id: string;
  label: string;
  layer: "hazard" | "logistics" | "economic" | "outcome";
}

export interface FcmEdge {
  source: string;
  target: string;
  weight: number;
  provenance: { citation: string; provisional: boolean; confidence: number };
}

export interface FcmMap {
  name: string;
  concepts: FcmConcept[];
  edges: FcmEdge[];
}

export function fetchFcmMap(): Promise<FcmMap> {
  return request<FcmMap>("/fcm/map");
}

export function simulateScenario(spec: ScenarioSpec): Promise<ScenarioResult> {
  return request<ScenarioResult>("/scenario/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
}
