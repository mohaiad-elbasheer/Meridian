// Advisor view: structured, rule-based interpretation of the last simulation run,
// with role lenses and a downloadable report. The future LLM assist plugs in here.

import { useState } from "react";
import type { Baseline, ScenarioResult } from "./api";
import { buildNarrative, ROLE_LABELS, type Role } from "./advisor";
import { downloadReport } from "./report";

interface Props {
  result: ScenarioResult | null;
  baseline: Baseline | null;
  onGoSimulate: () => void;
}

export function Advisor({ result, baseline, onGoSimulate }: Props) {
  const [role, setRole] = useState<Role>("supply_chain");
  if (!result || !baseline) {
    return (
      <div className="advisor advisor-empty">
        <div>
          <h1>Advisor</h1>
          <p>
            Run a simulation first — the Advisor reads your scenario definition and its
            results, explains them in plain language, and highlights what matters for
            your role.
          </p>
          <button className="run" style={{ maxWidth: 260 }} onClick={onGoSimulate}>
            Go to Simulation
          </button>
        </div>
      </div>
    );
  }
  const n = buildNarrative(result, baseline);
  return (
    <div className="advisor">
      <div className="advisor-col">
        <div className="advisor-head">
          <h1>Advisor</h1>
          <button className="csv" onClick={() => downloadReport(result, baseline)}>
            ⭳ download report (HTML)
          </button>
        </div>

        <section className="mon-section">
          <h2>Your scenario</h2>
          <p className="prose">{n.scenario}</p>
        </section>

        <section className="mon-section">
          <h2>What the simulation shows</h2>
          <p className="prose">{n.outcome}</p>
        </section>

        <section className="mon-section">
          <h2>Key drivers</h2>
          <ul className="prose-list">
            {n.drivers.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </section>

        <section className="mon-section">
          <h2>For your role</h2>
          <div className="view-toggle" style={{ marginBottom: 10 }}>
            {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
              <button key={r} className={role === r ? "active" : ""} onClick={() => setRole(r)}>
                {ROLE_LABELS[r]}
              </button>
            ))}
          </div>
          <ul className="prose-list">
            {n.roleNotes[role].map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>

        <section className="mon-section">
          <h2>Assumptions &amp; limitations</h2>
          <ul className="warnings">
            {n.limitations.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
