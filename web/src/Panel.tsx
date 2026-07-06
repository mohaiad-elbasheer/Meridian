import { useState } from "react";
import type {
  SavedScenario, ScenarioSpec, SignalsResponse, SourcesStatus,
} from "./api";

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
          {status?.database.error?.includes("static demo")
            ? "static demo — no live data sources in this build"
            : "database unreachable — serving bundled baselines"}
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

interface SignalsProps {
  signals: SignalsResponse | null;
  onApply: (suggested: Record<string, number>) => void;
}

export function Signals({ signals, onApply }: SignalsProps) {
  if (!signals?.available || signals.chokepoints.length === 0) return null;
  return (
    <section>
      <h2>Live signals — last {signals.window_days} days</h2>
      {signals.chokepoints.map((s) => (
        <div className="signal" key={s.chokepoint_id}>
          <div className="head">
            <span className="name">{s.label}</span>
            <span className="meta">
              {s.conflict_events > 0 && `${s.conflict_events} conflict evts `}
              {s.max_quake_mag > 0 && `M${s.max_quake_mag.toFixed(1)} quake `}
              {s.gdacs_max_level >= 2 && (s.gdacs_max_level >= 3 ? "RED alert" : "orange alert")}
            </span>
          </div>
          {Object.keys(s.suggested_clamps).length > 0 && (
            <button className="apply" onClick={() => onApply(s.suggested_clamps)}>
              apply suggested soft factors (
              {Object.entries(s.suggested_clamps)
                .map(([k, v]) => `${k} ${v.toFixed(2)}`)
                .join(", ")}
              )
            </button>
          )}
        </div>
      ))}
      <div className="baseline-note">advisory mapping — nothing is applied automatically</div>
    </section>
  );
}

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
      <div className="baseline-note">saves the current builder state ({spec.name})</div>
    </section>
  );
}
