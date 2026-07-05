// Static-demo implementations of the API surface (GitHub Pages build, VITE_DEMO=1).
// Baselines and the FCM spec are baked at build time from the Python engine
// (tools/gen_demo_data.py); scenarios persist in localStorage.

import type {
  Baseline, FcmMap, SavedScenario, ScenarioResult, ScenarioSpec, SourcesStatus,
} from "../api";
import baselineData from "./data/baseline.json";
import fcmData from "./data/fcm.json";
import { runScenario, type FcmSpecFull } from "./engine";

const baseline = baselineData as unknown as Baseline;
const fcmSpec = fcmData as unknown as FcmSpecFull;

const STORE_KEY = "meridian_demo_scenarios";

function readStore(): SavedScenario[] {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) ?? "[]") as SavedScenario[];
  } catch {
    return [];
  }
}

function writeStore(items: SavedScenario[]): void {
  localStorage.setItem(STORE_KEY, JSON.stringify(items));
}

export function fetchBaseline(): Promise<Baseline> {
  return Promise.resolve(baseline);
}

export function fetchFcmMap(): Promise<FcmMap> {
  return Promise.resolve(fcmSpec);
}

export function simulateScenario(spec: ScenarioSpec): Promise<ScenarioResult> {
  try {
    const result = runScenario(fcmSpec, baseline, spec);
    result.warnings = [
      "static demo: engine runs in your browser on the bundled synthetic seed — " +
        "the full platform computes on live PortWatch baselines",
      ...result.warnings,
    ];
    return Promise.resolve(result);
  } catch (e) {
    return Promise.reject(e instanceof Error ? e : new Error(String(e)));
  }
}

export function fetchSourcesStatus(): Promise<SourcesStatus> {
  return Promise.resolve({
    database: { reachable: false, error: "static demo — no live data sources" },
    tables: {},
  });
}

export function listScenarios(): Promise<SavedScenario[]> {
  return Promise.resolve(
    readStore().sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
  );
}

export function saveScenario(name: string, spec: ScenarioSpec): Promise<SavedScenario> {
  const now = new Date().toISOString();
  const item: SavedScenario = {
    id: crypto.randomUUID(), name, spec, created_at: now, updated_at: now,
  };
  writeStore([item, ...readStore()]);
  return Promise.resolve(item);
}

export function deleteScenario(id: string): Promise<void> {
  writeStore(readStore().filter((s) => s.id !== id));
  return Promise.resolve();
}
