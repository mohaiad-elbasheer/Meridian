import { useState } from "react";
import type {
  Baseline, NetworkNode, SavedScenario, ScenarioResult, ScenarioSpec, SourcesStatus,
} from "./api";
import { days, factor, pct, tons } from "./format";

interface SavedProps {
  saved: SavedScenario[] | null;
  spec: ScenarioSpec;
  onSave: (name: string) => Promise<void>;
  onLoad: (s: SavedScenario) => void;
  onDelete: (id: string) => Promise<void>;
}

export function SavedScenarios({ saved, spec, onSave, onLoad, onDelete }: SavedProps) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  if (saved === null) return null; // storage unavailable (no DB) — hide quietly
  return (
    <section>
      <h2>Saved scenarios</h2>
      {saved.length === 0 && <div className="empty">nothing saved yet</div>}
      {saved.map((s) => (
        <div className="saved-item" key={s.id}>
          <button className="load" title="load into the builder" onClick={() => onLoad(s)}>
            {s.name}
          </button>
          <span className="meta">
            −{Math.round(s.spec.capacity_reduction * 100)}% · {s.spec.duration_days}d
          </span>
          <button className="del" aria-label={`delete ${s.name}`} onClick={() => onDelete(s.id)}>
            ×
          </button>
        </div>
      ))}
      <div className="save-row">
        <input
          type="text" placeholder="name this scenario" value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button
          disabled={busy || !name.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              await onSave(name.trim());
              setName("");
            } finally {
              setBusy(false);
            }
          }}
        >
          Save
        </button>
      </div>
      <div className="baseline-note">
        saves the current builder state ({spec.name})
      </div>
    </section>
  );
}

const TABLE_LABELS: Record<string, string> = {
  chokepoint_daily: "PortWatch chokepoints",
  port_daily: "PortWatch ports",
  geo_events: "GDELT / USGS / GDACS",
};

export function Sources({ status }: { status: SourcesStatus | null }) {
  return (
    <section>
      <h2>Data sources</h2>
      {!status || !status.database.reachable ? (
        <div className="empty">
          database unreachable — serving bundled baselines
        </div>
      ) : (
        Object.entries(status.tables).map(([table, t]) => (
          <div className="kv" key={table}>
            <span className="k">{TABLE_LABELS[table] ?? table}</span>
            <span className="v">
              {t.rows > 0 ? `${t.rows} rows · to ${t.latest}` : "no data yet"}
            </span>
          </div>
        ))
      )}
    </section>
  );
}

interface ControlsProps {
  chokepoints: NetworkNode[];
  targetId: string;
  reduction: number;
  duration: number;
  clamps: Record<string, number>;
  running: boolean;
  onTarget: (id: string) => void;
  onReduction: (v: number) => void;
  onDuration: (v: number) => void;
  onClampsChange: (clamps: Record<string, number>) => void;
  onRun: () => void;
}

export function ScenarioControls(p: ControlsProps) {
  const target = p.chokepoints.find((c) => c.id === p.targetId);
  return (
    <section>
      <h2>Scenario</h2>
      <div className="field">
        <label htmlFor="cp">Chokepoint</label>
        <select id="cp" value={p.targetId} onChange={(e) => p.onTarget(e.target.value)}>
          {p.chokepoints.map((c) => (
            <option key={c.id} value={c.id}>{c.label ?? c.id}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="red">
          Capacity reduction <span className="value">−{Math.round(p.reduction * 100)}%</span>
        </label>
        <input
          id="red" type="range" min={5} max={100} step={5}
          value={Math.round(p.reduction * 100)}
          onChange={(e) => p.onReduction(Number(e.target.value) / 100)}
        />
      </div>
      <div className="field">
        <label htmlFor="dur">Duration (days)</label>
        <input
          id="dur" type="number" min={1} max={365} value={p.duration}
          onChange={(e) => p.onDuration(Math.max(1, Math.min(365, Number(e.target.value) || 1)))}
        />
      </div>
      <div className="field">
        <label className="check">
          <input
            type="checkbox" checked={p.clamps["armed_conflict"] === 1.0}
            onChange={(e) => {
              const next = { ...p.clamps };
              if (e.target.checked) next["armed_conflict"] = 1.0;
              else delete next["armed_conflict"];
              p.onClampsChange(next);
            }}
          />
          <span>armed-conflict escalation (clamps FCM concept to 1.0)</span>
        </label>
      </div>
      {Object.keys(p.clamps).length > 0 && (
        <div className="chips">
          {Object.entries(p.clamps).map(([id, v]) => (
            <span className="chip" key={id}>
              {id} ⊦ {v.toFixed(2)}
              <button
                aria-label={`release ${id}`}
                onClick={() => {
                  const next = { ...p.clamps };
                  delete next[id];
                  p.onClampsChange(next);
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <button className="run" disabled={p.running || !p.targetId} onClick={p.onRun}>
        {p.running ? "Running…" : "Run scenario"}
      </button>
      {target && (
        <div className="baseline-note">
          baseline: {tons(target.baseline_daily_tons ?? 0)}/day ·{" "}
          {target.baseline_daily_calls ?? "—"} calls/day
        </div>
      )}
    </section>
  );
}

export function Results({ result, baseline }: { result: ScenarioResult; baseline: Baseline }) {
  const labels = new Map(baseline.nodes.map((n) => [n.id, n.label ?? n.id]));
  const exposure = Object.entries(result.impact.country_exposure);
  const maxExposure = Math.max(...exposure.map(([, v]) => v), 1);
  const reroutes = result.impact.chokepoints.flatMap((c) => c.reroutes);
  return (
    <>
      <section>
        <h2>Impact — {result.scenario.duration_days} day window</h2>
        <div className="tiles">
          <div className="tile">
            <div className="num">{tons(result.impact.rerouted_tons)}</div>
            <div className="cap">rerouted</div>
          </div>
          <div className="tile">
            <div className="num">{tons(result.impact.delayed_tons)}</div>
            <div className="cap">delayed</div>
          </div>
          <div className="tile">
            <div className="num">{days(result.impact.avg_added_days)}</div>
            <div className="cap">avg added transit</div>
          </div>
        </div>
        {reroutes.length > 0 ? (
          <div style={{ marginTop: 10 }}>
            {reroutes.map((r) => (
              <div className="reroute" key={r.via}>
                via <span className="via">{labels.get(r.via) ?? r.via}</span>{" "}
                <span className="m">{tons(r.daily_tons)}/day, +{days(r.added_days)}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty" style={{ marginTop: 10 }}>
            no alternative route in network — all blocked volume is delayed
          </div>
        )}
      </section>

      <section>
        <h2>Import exposure (% of imports at risk)</h2>
        {exposure.map(([iso, v]) => (
          <div className="bar-row" key={iso}>
            <span className="iso">{iso}</span>
            <div className="track">
              <div className="fill" style={{ width: `${(v / maxExposure) * 100}%` }} />
            </div>
            <span className="val">{pct(v)}</span>
          </div>
        ))}
        {exposure.length === 0 && <div className="empty">none recorded</div>}
      </section>

      <section>
        <h2>FCM-modulated indices</h2>
        {Object.entries(result.network_multipliers).map(([k, v]) => (
          <div className="kv" key={k}>
            <span className="k">{k}</span>
            <span className="v">{factor(v)}</span>
          </div>
        ))}
        <div className="kv">
          <span className="k">FCM convergence</span>
          <span className="v">{result.fcm.converged ? `${result.fcm.steps} steps` : "not converged"}</span>
        </div>
        <div className="kv">
          <span className="k">edge weights provisional</span>
          <span className="v">{result.provisional_edges}/{result.total_edges}</span>
        </div>
      </section>

      {result.warnings.length > 0 && (
        <section>
          <h2>Data quality</h2>
          <ul className="warnings">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
