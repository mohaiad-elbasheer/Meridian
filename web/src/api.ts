// Typed client for the Meridian API (proxied under /api in dev, see vite.config.ts).
// With VITE_DEMO=1 (GitHub Pages build) every call is served by the in-browser demo
// implementation instead — the demo chunk is tree-shaken out of normal builds.

export const IS_DEMO = import.meta.env.VITE_DEMO === "1";

function demoApi() {
  return import("./demo/api");
}

export const VESSEL_CLASSES = [
  "container", "dry_bulk", "general_cargo", "roro", "tanker",
] as const;
export type VesselClass = (typeof VESSEL_CLASSES)[number];

export const CLASS_LABELS: Record<VesselClass, string> = {
  container: "Container",
  dry_bulk: "Dry bulk",
  general_cargo: "General cargo",
  roro: "Ro-ro (vehicles)",
  tanker: "Tanker (liquids)",
};

export type Cause = "unspecified" | "conflict" | "natural_hazard" | "accident" | "policy";

export const CAUSE_LABELS: Record<Cause, string> = {
  unspecified: "Unspecified",
  conflict: "Armed conflict",
  natural_hazard: "Natural hazard",
  accident: "Accident / blockage",
  policy: "Sanctions / policy",
};

export interface NetworkNode {
  id: string;
  type: "chokepoint" | "port" | "country";
  label?: string;
  lat?: number;
  lon?: number;
  baseline_daily_calls?: number;
  baseline_daily_tons?: number;
  capacity_daily_tons?: number;
  class_shares?: Record<string, number> | null;
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
  class_reductions?: Record<string, number>;
  cause?: Cause;
  fcm_clamps?: Clamp[];
  value_per_ton_usd?: Record<string, number>;
}

export interface ClassImpact {
  share: number;
  reduction: number;
  blocked_tons: number;
  rerouted_tons: number;
  delayed_tons: number;
  value_delayed_usd: number;
}

export interface Kpis {
  baseline_window_tons: number;
  blocked_tons: number;
  rerouted_tons: number;
  delayed_tons: number;
  delayed_share_of_window: number;
  avg_added_days: number;
  value_delayed_usd: number;
  value_rerouted_usd: number;
  per_class: Record<string, ClassImpact>;
  reroute_cost_factor: number;
  port_dwell_factor: number;
  landed_cost_activation: number;
  supply_availability_activation: number;
  top_exposed_countries: Record<string, number>;
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
  auto_clamps: Record<string, number>;
  network_multipliers: Record<string, number>;
  impact: {
    rerouted_tons: number;
    delayed_tons: number;
    avg_added_days: number;
    country_exposure: Record<string, number>;
    chokepoints: ChokepointImpact[];
  };
  kpis: Kpis;
  assumptions: {
    value_per_ton_usd: Record<string, number>;
    value_per_ton_provisional: boolean;
    class_shares: Record<string, number>;
    class_shares_source: string;
  };
  provisional_edges: number;
  total_edges: number;
  warnings: string[];
}

export interface ChokepointSignal {
  chokepoint_id: string;
  label: string;
  events: number;
  conflict_events: number;
  max_quake_mag: number;
  gdacs_max_level: number;
  suggested_clamps: Record<string, number>;
}

export interface SignalsResponse {
  available: boolean;
  window_days: number;
  note?: string;
  chokepoints: ChokepointSignal[];
}

export async function fetchSignals(): Promise<SignalsResponse> {
  if (IS_DEMO) return { available: false, window_days: 7, chokepoints: [] };
  return request<SignalsResponse>("/signals/chokepoints");
}

export interface SeriesPoint {
  date: string;
  transit_calls: number | null;
  trade_tons: number | null;
}

export interface SeriesResponse {
  available: boolean;
  chokepoint_id?: string;
  label?: string;
  days?: number;
  points: SeriesPoint[];
}

export async function fetchTimeseries(chokepointId: string, days = 90): Promise<SeriesResponse> {
  if (IS_DEMO) return { available: false, points: [] };
  return request<SeriesResponse>(`/timeseries/chokepoints/${chokepointId}?days=${days}`);
}

export interface TradePartner {
  partner: string;
  import_usd: number;
  share: number;
}

export interface TradeDependencies {
  available: boolean;
  year?: number;
  source?: string;
  reporters: Record<string, { total_import_usd: number; partners: TradePartner[] }>;
}

export async function fetchTradeDependencies(): Promise<TradeDependencies> {
  if (IS_DEMO) return { available: false, reporters: {} };
  return request<TradeDependencies>("/trade/dependencies");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 300)}`);
  }
  return (await res.json()) as T;
}

export async function fetchBaseline(): Promise<Baseline> {
  if (IS_DEMO) return (await demoApi()).fetchBaseline();
  return request<Baseline>("/network/baseline");
}

export async function fetchSourcesStatus(): Promise<SourcesStatus> {
  if (IS_DEMO) return (await demoApi()).fetchSourcesStatus();
  return request<SourcesStatus>("/sources/status");
}

export interface SavedScenario {
  id: string;
  name: string;
  spec: ScenarioSpec;
  created_at: string;
  updated_at: string;
}

export async function listScenarios(): Promise<SavedScenario[]> {
  if (IS_DEMO) return (await demoApi()).listScenarios();
  return request<SavedScenario[]>("/scenarios");
}

export async function saveScenario(name: string, spec: ScenarioSpec): Promise<SavedScenario> {
  if (IS_DEMO) return (await demoApi()).saveScenario(name, spec);
  return request<SavedScenario>("/scenarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, spec }),
  });
}

export async function deleteScenario(id: string): Promise<void> {
  if (IS_DEMO) return (await demoApi()).deleteScenario(id);
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

export async function fetchFcmMap(): Promise<FcmMap> {
  if (IS_DEMO) return (await demoApi()).fetchFcmMap();
  return request<FcmMap>("/fcm/map");
}

export async function simulateScenario(spec: ScenarioSpec): Promise<ScenarioResult> {
  if (IS_DEMO) return (await demoApi()).simulateScenario(spec);
  return request<ScenarioResult>("/scenario/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
}
