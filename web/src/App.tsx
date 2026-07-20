import { useCallback, useEffect, useMemo, useState } from "react";
import {
  IS_DEMO,
  deleteScenario, fetchBaseline, fetchSignals, fetchSourcesStatus,
  fetchTradeDependencies, listScenarios, saveScenario, simulateScenario,
  type Baseline, type SavedScenario, type ScenarioResult, type SignalsResponse,
  type SourcesStatus, type TradeDependencies, type VesselClass,
} from "./api";
import { Monitoring } from "./Monitoring";
import {
  builderFromSpec, buildSpec, initialBuilderValues, ScenarioBuilder, type BuilderValues,
} from "./Builder";
import { Advisor } from "./Advisor";
import { Dashboard } from "./Dashboard";
import { FcmCanvas } from "./FcmCanvas";
import { MapView } from "./MapView";
import { SavedScenarios, Sources } from "./Panel";

export function App() {
  const [mainView, setMainView] = useState<"monitoring" | "simulation" | "advisor">("simulation");
  const [view, setView] = useState<"map" | "fcm">("map");
  const [trade, setTrade] = useState<TradeDependencies | null>(null);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [builder, setBuilder] = useState<BuilderValues>(initialBuilderValues("suez_canal"));
  const [clamps, setClamps] = useState<Record<string, number>>({});
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourcesStatus | null>(null);
  const [signals, setSignals] = useState<SignalsResponse | null>(null);
  const [saved, setSaved] = useState<SavedScenario[] | null>(null);

  const refreshSaved = useCallback(() => {
    listScenarios().then(setSaved).catch(() => setSaved(null));
  }, []);

  useEffect(() => {
    fetchBaseline().then(setBaseline).catch((e: Error) => setError(e.message));
    fetchSourcesStatus().then(setSources).catch(() => setSources(null));
    fetchSignals().then(setSignals).catch(() => setSignals(null));
    fetchTradeDependencies().then(setTrade).catch(() => setTrade(null));
    refreshSaved();
  }, [refreshSaved]);

  const chokepoints = useMemo(
    () =>
      (baseline?.nodes ?? [])
        .filter((n) => n.type === "chokepoint")
        .sort((a, b) => (a.label ?? a.id).localeCompare(b.label ?? b.id)),
    [baseline],
  );

  const spec = useMemo(() => buildSpec(builder, clamps), [builder, clamps]);

  function patchBuilder(patch: Partial<BuilderValues>) {
    setBuilder((prev) => ({ ...prev, ...patch }));
    if (patch.targetId) setResult(null);
  }

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
    setBuilder((prev) => builderFromSpec(s.spec, prev));
    setClamps(Object.fromEntries((s.spec.fcm_clamps ?? []).map((c) => [c.concept_id, c.value])));
    setResult(null);
  }

  return (
    <div className="app">
      <header className="header">
        <span className="wordmark"><span>◈</span> MERIDIAN</span>
        <span className="tagline">near-real-time signals · daily-resolution flows</span>
        <div className="view-toggle primary">
          <button className={mainView === "monitoring" ? "active" : ""}
            onClick={() => setMainView("monitoring")}>
            Monitoring
          </button>
          <button className={mainView === "simulation" ? "active" : ""}
            onClick={() => setMainView("simulation")}>
            Simulation
          </button>
          <button className={mainView === "advisor" ? "active" : ""}
            onClick={() => setMainView("advisor")}>
            Advisor
          </button>
        </div>
        {mainView === "simulation" && (
          <div className="view-toggle">
            <button className={view === "map" ? "active" : ""} onClick={() => setView("map")}>
              Map
            </button>
            <button className={view === "fcm" ? "active" : ""} onClick={() => setView("fcm")}>
              Soft factors
            </button>
          </div>
        )}
        <span className="spacer" />
        {IS_DEMO && <span className="flag">static demo</span>}
        {baseline &&
          (baseline.provenance === "mixed" ? (
            <span className="flag" title={baseline.source}>
              mixed data · {baseline.coverage?.chokepoints_observed ?? "?"}/
              {baseline.coverage?.chokepoints_total ?? "?"} observed
            </span>
          ) : baseline.synthetic ? (
            <span className="flag" title={baseline.source}>synthetic seed</span>
          ) : (
            <span className="flag neutral" title={baseline.source}>portwatch baselines</span>
          ))}
        <span className="flag neutral">macro v0</span>
      </header>
      {mainView === "advisor" ? (
        <Advisor
          result={result}
          baseline={baseline}
          onGoSimulate={() => setMainView("simulation")}
        />
      ) : mainView === "monitoring" ? (
        <Monitoring
          baseline={baseline}
          signals={signals}
          sources={sources}
          trade={trade}
          onApplySignals={(suggested) => setClamps((prev) => ({ ...suggested, ...prev }))}
          onSimulate={(id) => {
            patchBuilder({ targetId: id });
            setMainView("simulation");
          }}
        />
      ) : (
      <div className="body">
        {view === "map" ? (
          <MapView
            baseline={baseline}
            result={result}
            targetId={builder.targetId}
            onSelect={(id) => patchBuilder({ targetId: id })}
          />
        ) : (
          <FcmCanvas clamps={clamps} onClampsChange={setClamps} />
        )}
        <aside className="panel">
          <ScenarioBuilder
            chokepoints={chokepoints}
            values={builder}
            clamps={clamps}
            running={running}
            onChange={patchBuilder}
            onClampsChange={setClamps}
            onRun={run}
          />
          {error && (
            <section>
              <div className="error">{error}</div>
            </section>
          )}
          {result && baseline ? (
            <Dashboard result={result} baseline={baseline} />
          ) : (
            !error && (
              <section>
                <div className="empty">
                  Describe a disruption above and run it. The dashboard reports delayed and
                  rerouted volumes with units, cargo value at risk under stated assumptions,
                  added transit time, country import exposure, and the market &amp; risk
                  indices the scenario produced — each with a plain-language explanation
                  behind the ⓘ buttons.
                </div>
              </section>
            )
          )}
          <SavedScenarios
            saved={saved}
            spec={spec}
            onSave={async (name) => {
              try {
                await saveScenario(name, spec);
                refreshSaved();
              } catch (e) {
                setError(`could not save scenario — ${(e as Error).message}`);
              }
            }}
            onLoad={loadScenario}
            onDelete={async (id) => {
              try {
                await deleteScenario(id);
                refreshSaved();
              } catch (e) {
                setError(`could not delete scenario — ${(e as Error).message}`);
              }
            }}
          />
          <Sources status={sources} />
        </aside>
      </div>
      )}
    </div>
  );
}
