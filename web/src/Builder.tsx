// Scenario builder: Guided mode for non-specialists (cause, severity, affected
// traffic, duration), Expert mode adding per-class reductions, valuation
// assumptions, and soft-factor clamps (the causal-map layer, kept jargon-free here).

import {
  CAUSE_LABELS, CLASS_LABELS, VESSEL_CLASSES,
  type Cause, type NetworkNode, type ScenarioSpec, type VesselClass,
} from "./api";
import { tons } from "./format";

export interface BuilderValues {
  targetId: string;
  severity: number;                       // 0..1 capacity loss
  duration: number;                       // days
  cause: Cause;
  enabled: Record<VesselClass, boolean>;  // guided: which traffic is affected
  expert: boolean;
  classReductions: Record<VesselClass, number>;  // expert per-class 0..1
  valuePerTon: Record<VesselClass, number>;      // USD/ton assumptions
}

export const DEFAULT_VALUE_PER_TON: Record<VesselClass, number> = {
  container: 4000, dry_bulk: 120, general_cargo: 900, roro: 3000, tanker: 550,
};

export function initialBuilderValues(targetId: string): BuilderValues {
  return {
    targetId,
    severity: 0.8,
    duration: 14,
    cause: "unspecified",
    enabled: Object.fromEntries(VESSEL_CLASSES.map((c) => [c, true])) as
      Record<VesselClass, boolean>,
    expert: false,
    classReductions: Object.fromEntries(VESSEL_CLASSES.map((c) => [c, 0.8])) as
      Record<VesselClass, number>,
    valuePerTon: { ...DEFAULT_VALUE_PER_TON },
  };
}

export function buildSpec(v: BuilderValues, clamps: Record<string, number>): ScenarioSpec {
  let classReductions: Record<string, number> | undefined;
  if (v.expert) {
    classReductions = { ...v.classReductions };
  } else if (VESSEL_CLASSES.some((c) => !v.enabled[c])) {
    classReductions = Object.fromEntries(
      VESSEL_CLASSES.map((c) => [c, v.enabled[c] ? v.severity : 0]),
    );
  }
  return {
    name: `${v.targetId} −${Math.round(v.severity * 100)}% for ${v.duration}d`,
    target_chokepoint_id: v.targetId,
    capacity_reduction: v.severity,
    duration_days: v.duration,
    class_reductions: classReductions,
    cause: v.cause,
    fcm_clamps: Object.entries(clamps).map(([concept_id, value]) => ({ concept_id, value })),
    value_per_ton_usd: v.valuePerTon,
  };
}

interface Props {
  chokepoints: NetworkNode[];
  values: BuilderValues;
  clamps: Record<string, number>;
  running: boolean;
  onChange: (patch: Partial<BuilderValues>) => void;
  onClampsChange: (clamps: Record<string, number>) => void;
  onRun: () => void;
}

export function ScenarioBuilder({
  chokepoints, values: v, clamps, running, onChange, onClampsChange, onRun,
}: Props) {
  const target = chokepoints.find((c) => c.id === v.targetId);
  return (
    <section>
      <h2>
        Scenario
        <span className="mode-switch">
          <button className={v.expert ? "" : "on"} onClick={() => onChange({ expert: false })}>
            Guided
          </button>
          <button className={v.expert ? "on" : ""} onClick={() => onChange({ expert: true })}>
            Expert
          </button>
        </span>
      </h2>

      <div className="field">
        <label htmlFor="cp">Chokepoint</label>
        <select id="cp" value={v.targetId}
          onChange={(e) => onChange({ targetId: e.target.value })}>
          {chokepoints.map((c) => (
            <option key={c.id} value={c.id}>{c.label ?? c.id}</option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="cause">What happens?</label>
        <select id="cause" value={v.cause}
          onChange={(e) => onChange({ cause: e.target.value as Cause })}>
          {Object.entries(CAUSE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>{label}</option>
          ))}
        </select>
        <div className="hint">
          the cause automatically drives market &amp; risk conditions — experts can
          override them in the Soft factors view
        </div>
      </div>

      <div className="field">
        <label htmlFor="sev">
          Capacity loss <span className="value">−{Math.round(v.severity * 100)}%</span>
        </label>
        <input id="sev" type="range" min={5} max={100} step={5}
          value={Math.round(v.severity * 100)}
          onChange={(e) => {
            const sev = Number(e.target.value) / 100;
            onChange({
              severity: sev,
              classReductions: Object.fromEntries(VESSEL_CLASSES.map(
                (c) => [c, v.enabled[c] ? sev : 0])) as Record<VesselClass, number>,
            });
          }}
        />
      </div>

      {!v.expert && (
        <div className="field">
          <label>Affected traffic</label>
          <div className="class-grid">
            {VESSEL_CLASSES.map((c) => (
              <label className="check" key={c}>
                <input type="checkbox" checked={v.enabled[c]}
                  onChange={(e) => onChange({
                    enabled: { ...v.enabled, [c]: e.target.checked },
                  })}
                />
                <span>{CLASS_LABELS[c]}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {v.expert && (
        <div className="field">
          <label>Capacity loss per vessel class</label>
          {VESSEL_CLASSES.map((c) => (
            <div className="class-slider" key={c}>
              <span className="cls">{CLASS_LABELS[c]}</span>
              <input type="range" min={0} max={100} step={5}
                value={Math.round(v.classReductions[c] * 100)}
                onChange={(e) => onChange({
                  classReductions: {
                    ...v.classReductions, [c]: Number(e.target.value) / 100,
                  },
                })}
              />
              <span className="value">−{Math.round(v.classReductions[c] * 100)}%</span>
            </div>
          ))}
        </div>
      )}

      <div className="field">
        <label htmlFor="dur">Duration (days)</label>
        <input id="dur" type="number" min={1} max={365} value={v.duration}
          onChange={(e) => onChange({
            duration: Math.max(1, Math.min(365, Number(e.target.value) || 1)),
          })}
        />
      </div>

      {v.expert && (
        <details className="assumptions">
          <summary>Valuation assumptions (USD per ton)</summary>
          {VESSEL_CLASSES.map((c) => (
            <div className="class-slider" key={c}>
              <span className="cls">{CLASS_LABELS[c]}</span>
              <input type="number" min={0} value={v.valuePerTon[c]}
                onChange={(e) => onChange({
                  valuePerTon: { ...v.valuePerTon, [c]: Number(e.target.value) || 0 },
                })}
              />
              <span className="value">$/t</span>
            </div>
          ))}
          <div className="hint">provisional defaults — set them to your book of business</div>
        </details>
      )}

      {Object.keys(clamps).length > 0 && (
        <div className="chips">
          {Object.entries(clamps).map(([id, val]) => (
            <span className="chip" key={id}>
              {id} ⊦ {val.toFixed(2)}
              <button aria-label={`release ${id}`} onClick={() => {
                const next = { ...clamps };
                delete next[id];
                onClampsChange(next);
              }}>×</button>
            </span>
          ))}
        </div>
      )}

      <button className="run" disabled={running || !v.targetId} onClick={onRun}>
        {running ? "Running…" : "Run scenario"}
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
