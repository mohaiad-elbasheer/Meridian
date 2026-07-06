// Results dashboard: headline KPIs with dynamic plain-language explanations,
// per-class impact, country exposure, market & risk indices, assumptions.

import { useState } from "react";
import { CLASS_LABELS, VESSEL_CLASSES, type Baseline, type ScenarioResult } from "./api";
import { days, factor, pct, tons, usd } from "./format";

function Info({ title, text }: { title: string; text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="info">
      <button aria-label={`explain ${title}`} onClick={() => setOpen(!open)}>i</button>
      {open && (
        <span className="info-pop" onClick={() => setOpen(false)}>
          <strong>{title}</strong>
          {text}
        </span>
      )}
    </span>
  );
}

export function Dashboard({ result, baseline }: { result: ScenarioResult; baseline: Baseline }) {
  const k = result.kpis;
  const labels = new Map(baseline.nodes.map((n) => [n.id, n.label ?? n.id]));
  const target = labels.get(result.scenario.target_chokepoint_id) ??
    result.scenario.target_chokepoint_id;
  const d = result.scenario.duration_days;
  const reroutes = result.impact.chokepoints.flatMap((c) => c.reroutes);
  const activeClasses = VESSEL_CLASSES.filter((c) => (k.per_class[c]?.blocked_tons ?? 0) > 0);
  const maxBlocked = Math.max(...activeClasses.map((c) => k.per_class[c].blocked_tons), 1);
  const exposure = Object.entries(k.top_exposed_countries);
  const maxExposure = Math.max(...exposure.map(([, v]) => v), 1);

  return (
    <>
      <section>
        <h2>Impact — {target}, {d}-day window</h2>
        <div className="tiles tiles-2">
          <div className="tile">
            <div className="num">{tons(k.delayed_tons)}</div>
            <div className="cap">
              delayed / undelivered
              <Info title="Delayed volume"
                text={`${tons(k.delayed_tons)} cannot transit or find an alternative route
                during the ${d}-day window — ${pct(k.delayed_share_of_window * 100)} of the
                ${tons(k.baseline_window_tons)} that normally moves through ${target} in that
                period. For importers this is inventory at risk; for insurers, potential
                delay and demurrage exposure.`}
              />
            </div>
          </div>
          <div className="tile">
            <div className="num">{usd(k.value_delayed_usd)}</div>
            <div className="cap">
              cargo value delayed
              <Info title="Cargo value delayed"
                text={`Delayed tonnage × assumed cargo value per vessel class (editable in
                Expert mode). A first-order exposure figure — not a loss estimate: cargo is
                late, not destroyed. Rerouted cargo (${usd(k.value_rerouted_usd)}) arrives
                ~${days(k.avg_added_days)} late instead.`}
              />
            </div>
          </div>
          <div className="tile">
            <div className="num">{tons(k.rerouted_tons)}</div>
            <div className="cap">
              rerouted
              <Info title="Rerouted volume"
                text={`Volume that diverts to alternative routes with spare capacity${
                  reroutes.length
                    ? ` (${reroutes.map((r) => labels.get(r.via) ?? r.via).join(", ")})`
                    : ""
                }. It still arrives — on average ${days(k.avg_added_days)} later, at higher
                freight cost (see indices below).`}
              />
            </div>
          </div>
          <div className="tile">
            <div className="num">{days(k.avg_added_days)}</div>
            <div className="cap">
              avg added transit
              <Info title="Added transit time"
                text={`Tonnage-weighted extra sailing days on the rerouted volume, including
                congestion dwell at the receiving route when soft factors raise it. Lead-time
                planners should add this to contracted delivery windows.`}
              />
            </div>
          </div>
        </div>
        {reroutes.length === 0 && (
          <div className="empty" style={{ marginTop: 8 }}>
            no alternative route exists in the network — all blocked volume is delayed
          </div>
        )}
      </section>

      {activeClasses.length > 0 && (
        <section>
          <h2>
            By vessel class
            <Info title="Vessel classes"
              text="PortWatch observes traffic by vessel class — the standard proxy for
              cargo type: containers (consumer/manufactured goods), dry bulk (grain, ore,
              coal), general cargo, ro-ro (vehicles), tankers (oil, gas, chemicals)."
            />
          </h2>
          {activeClasses.map((c) => {
            const ci = k.per_class[c];
            return (
              <div className="bar-row bar-row-wide" key={c}>
                <span className="iso">{CLASS_LABELS[c]}</span>
                <div className="track">
                  <div className="fill" style={{ width: `${(ci.blocked_tons / maxBlocked) * 100}%` }} />
                </div>
                <span className="val">{tons(ci.blocked_tons)}</span>
                <span className="sub">
                  −{Math.round(ci.reduction * 100)}% · {tons(ci.delayed_tons)} delayed ·{" "}
                  {usd(ci.value_delayed_usd)}
                </span>
              </div>
            );
          })}
        </section>
      )}

      <section>
        <h2>
          Import exposure (% of imports at risk)
          <Info title="Country import exposure"
            text="Share of each country's seaborne imports that normally transits the
            disrupted chokepoint, scaled by the capacity cut. A policy-maker's first
            screen for which trading partners feel this scenario. Shares are curated v0
            values until UN Comtrade ingestion replaces them with data."
          />
        </h2>
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
        <h2>
          Market &amp; risk indices
          <Info title="Market & risk indices"
            text="Soft factors — escalation, war-risk insurance, congestion, freight
            sentiment — modeled as a causal map that reacts to the scenario definition
            (and to expert overrides in the Soft factors view). Indices are multipliers
            and directional pressures, not price forecasts."
          />
        </h2>
        <div className="kv">
          <span className="k">reroute cost index</span>
          <span className="v">{factor(k.reroute_cost_factor)}</span>
        </div>
        <div className="kv">
          <span className="k">port congestion dwell</span>
          <span className="v">{factor(k.port_dwell_factor)}</span>
        </div>
        <div className="kv">
          <span className="k">landed-cost pressure (−1…1)</span>
          <span className="v">{k.landed_cost_activation.toFixed(2)}</span>
        </div>
        <div className="kv">
          <span className="k">supply availability (−1…1)</span>
          <span className="v">{k.supply_availability_activation.toFixed(2)}</span>
        </div>
        {Object.keys(result.auto_clamps).length > 0 && (
          <div className="chips">
            {Object.entries(result.auto_clamps).map(([id, v]) => (
              <span className="chip neutral" key={id} title="derived from the scenario definition">
                auto · {id} ⊦ {v.toFixed(2)}
              </span>
            ))}
          </div>
        )}
      </section>

      {result.warnings.length > 0 && (
        <section>
          <h2>Assumptions &amp; data quality</h2>
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
