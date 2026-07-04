import type { Baseline, NetworkNode, ScenarioResult } from "./api";
import { days, factor, pct, tons } from "./format";

interface ControlsProps {
  chokepoints: NetworkNode[];
  targetId: string;
  reduction: number;
  duration: number;
  escalation: boolean;
  running: boolean;
  onTarget: (id: string) => void;
  onReduction: (v: number) => void;
  onDuration: (v: number) => void;
  onEscalation: (v: boolean) => void;
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
            type="checkbox" checked={p.escalation}
            onChange={(e) => p.onEscalation(e.target.checked)}
          />
          <span>armed-conflict escalation (clamps FCM concept to 1.0)</span>
        </label>
      </div>
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
