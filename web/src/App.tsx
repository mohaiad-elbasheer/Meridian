import { useEffect, useMemo, useState } from "react";
import {
  fetchBaseline, simulateScenario,
  type Baseline, type ScenarioResult, type ScenarioSpec,
} from "./api";
import { MapView } from "./MapView";
import { Results, ScenarioControls } from "./Panel";

export function App() {
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [targetId, setTargetId] = useState("suez_canal");
  const [reduction, setReduction] = useState(0.8);
  const [duration, setDuration] = useState(14);
  const [escalation, setEscalation] = useState(false);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBaseline().then(setBaseline).catch((e: Error) => setError(e.message));
  }, []);

  const chokepoints = useMemo(
    () =>
      (baseline?.nodes ?? [])
        .filter((n) => n.type === "chokepoint")
        .sort((a, b) => (a.label ?? a.id).localeCompare(b.label ?? b.id)),
    [baseline],
  );

  async function run() {
    setRunning(true);
    setError(null);
    const spec: ScenarioSpec = {
      name: `${targetId} −${Math.round(reduction * 100)}% for ${duration}d`,
      target_chokepoint_id: targetId,
      capacity_reduction: reduction,
      duration_days: duration,
      fcm_clamps: escalation ? [{ concept_id: "armed_conflict", value: 1.0 }] : [],
    };
    try {
      setResult(await simulateScenario(spec));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <span className="wordmark"><span>◈</span> MERIDIAN</span>
        <span className="tagline">near-real-time signals · daily-resolution flows</span>
        <span className="spacer" />
        {baseline?.synthetic && <span className="flag">synthetic seed</span>}
        <span className="flag neutral">macro v0</span>
      </header>
      <div className="body">
        <MapView
          baseline={baseline}
          result={result}
          targetId={targetId}
          onSelect={(id) => {
            setTargetId(id);
            setResult(null);
          }}
        />
        <aside className="panel">
          <ScenarioControls
            chokepoints={chokepoints}
            targetId={targetId}
            reduction={reduction}
            duration={duration}
            escalation={escalation}
            running={running}
            onTarget={(id) => {
              setTargetId(id);
              setResult(null);
            }}
            onReduction={setReduction}
            onDuration={setDuration}
            onEscalation={setEscalation}
            onRun={run}
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
                  with the FCM soft-factor indices that modulated them.
                </div>
              </section>
            )
          )}
        </aside>
      </div>
    </div>
  );
}
