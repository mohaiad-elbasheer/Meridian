import { useCallback, useEffect, useMemo, useState } from "react";
import {
  deleteScenario, fetchBaseline, fetchSourcesStatus, listScenarios, saveScenario,
  simulateScenario,
  type Baseline, type SavedScenario, type ScenarioResult, type ScenarioSpec,
  type SourcesStatus,
} from "./api";
import { FcmCanvas } from "./FcmCanvas";
import { MapView } from "./MapView";
import { Results, SavedScenarios, ScenarioControls, Sources } from "./Panel";

export function App() {
  const [view, setView] = useState<"map" | "fcm">("map");
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [targetId, setTargetId] = useState("suez_canal");
  const [reduction, setReduction] = useState(0.8);
  const [duration, setDuration] = useState(14);
  const [clamps, setClamps] = useState<Record<string, number>>({});
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourcesStatus | null>(null);
  const [saved, setSaved] = useState<SavedScenario[] | null>(null);

  const refreshSaved = useCallback(() => {
    listScenarios().then(setSaved).catch(() => setSaved(null));
  }, []);

  useEffect(() => {
    fetchBaseline().then(setBaseline).catch((e: Error) => setError(e.message));
    fetchSourcesStatus().then(setSources).catch(() => setSources(null));
    refreshSaved();
  }, [refreshSaved]);

  const chokepoints = useMemo(
    () =>
      (baseline?.nodes ?? [])
        .filter((n) => n.type === "chokepoint")
        .sort((a, b) => (a.label ?? a.id).localeCompare(b.label ?? b.id)),
    [baseline],
  );

  const spec: ScenarioSpec = useMemo(
    () => ({
      name: `${targetId} −${Math.round(reduction * 100)}% for ${duration}d`,
      target_chokepoint_id: targetId,
      capacity_reduction: reduction,
      duration_days: duration,
      fcm_clamps: Object.entries(clamps).map(([concept_id, value]) => ({ concept_id, value })),
    }),
    [targetId, reduction, duration, clamps],
  );

  async function run() {
    setRunning(true);
    setError(null);
    try {
      setResult(await simulateScenario(spec));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  function loadScenario(s: SavedScenario) {
    setTargetId(s.spec.target_chokepoint_id);
    setReduction(s.spec.capacity_reduction);
    setDuration(s.spec.duration_days);
    setClamps(Object.fromEntries((s.spec.fcm_clamps ?? []).map((c) => [c.concept_id, c.value])));
    setResult(null);
  }

  return (
    <div className="app">
      <header className="header">
        <span className="wordmark"><span>◈</span> MERIDIAN</span>
        <span className="tagline">near-real-time signals · daily-resolution flows</span>
        <div className="view-toggle">
          <button className={view === "map" ? "active" : ""} onClick={() => setView("map")}>
            Map
          </button>
          <button className={view === "fcm" ? "active" : ""} onClick={() => setView("fcm")}>
            Causal map
          </button>
        </div>
        <span className="spacer" />
        {baseline &&
          (baseline.synthetic ? (
            <span className="flag" title={baseline.source}>synthetic seed</span>
          ) : (
            <span className="flag neutral" title={baseline.source}>portwatch baselines</span>
          ))}
        <span className="flag neutral">macro v0</span>
      </header>
      <div className="body">
        {view === "map" ? (
          <MapView
            baseline={baseline}
            result={result}
            targetId={targetId}
            onSelect={(id) => {
              setTargetId(id);
              setResult(null);
            }}
          />
        ) : (
          <FcmCanvas clamps={clamps} onClampsChange={setClamps} />
        )}
        <aside className="panel">
          <ScenarioControls
            chokepoints={chokepoints}
            targetId={targetId}
            reduction={reduction}
            duration={duration}
            clamps={clamps}
            running={running}
            onTarget={(id) => {
              setTargetId(id);
              setResult(null);
            }}
            onReduction={setReduction}
            onDuration={setDuration}
            onClampsChange={setClamps}
            onRun={run}
          />
          <SavedScenarios
            saved={saved}
            spec={spec}
            onSave={async (name) => {
              await saveScenario(name, spec);
              refreshSaved();
            }}
            onLoad={loadScenario}
            onDelete={async (id) => {
              await deleteScenario(id);
              refreshSaved();
            }}
          />
          {error && (
            <section>
              <div className="error">{error}</div>
            </section>
          )}
          {result && baseline ? (
            <Results result={result} baseline={baseline} />
          ) : (
            !error && (
              <section>
                <div className="empty">
                  Configure a disruption and run it. Results show rerouted and delayed
                  volumes in metric tons, added transit days, and country import exposure —
                  with the FCM soft-factor indices that modulated them. Set soft-factor
                  clamps in the causal-map view.
                </div>
              </section>
            )
          )}
          <Sources status={sources} />
        </aside>
      </div>
    </div>
  );
}
