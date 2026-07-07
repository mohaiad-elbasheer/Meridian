// Self-contained HTML report of a simulation run: scenario definition, narrative
// interpretation, KPI tables, assumptions, and data-quality notes. Print-friendly.

import { CLASS_LABELS, VESSEL_CLASSES, type Baseline, type ScenarioResult } from "./api";
import { buildNarrative, ROLE_LABELS, type Role } from "./advisor";
import { days, factor, pct, tons, usd } from "./format";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function buildReportHtml(result: ScenarioResult, baseline: Baseline): string {
  const n = buildNarrative(result, baseline);
  const k = result.kpis;
  const s = result.scenario;
  const target = baseline.nodes.find((x) => x.id === s.target_chokepoint_id)?.label ??
    s.target_chokepoint_id;
  const now = new Date().toISOString().slice(0, 16).replace("T", " ");

  const classRows = VESSEL_CLASSES.filter((c) => (k.per_class[c]?.blocked_tons ?? 0) > 0)
    .map((c) => {
      const ci = k.per_class[c];
      return `<tr><td>${CLASS_LABELS[c]}</td><td>−${Math.round(ci.reduction * 100)}%</td>
        <td>${tons(ci.blocked_tons)}</td><td>${tons(ci.delayed_tons)}</td>
        <td>${usd(ci.value_delayed_usd)}</td></tr>`;
    }).join("");

  const exposureRows = Object.entries(k.top_exposed_countries)
    .map(([iso, v]) => `<tr><td>${iso}</td><td>${pct(v)}</td></tr>`).join("");

  const roleBlocks = (Object.keys(ROLE_LABELS) as Role[]).map((r) => `
    <h3>${ROLE_LABELS[r]}</h3>
    <ul>${n.roleNotes[r].map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`).join("");

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Meridian scenario report — ${esc(target)}</title>
<style>
  body{font-family:Georgia,'Times New Roman',serif;color:#1a1d23;max-width:820px;
       margin:32px auto;padding:0 24px;line-height:1.55}
  h1{font-size:22px;border-bottom:2px solid #1a1d23;padding-bottom:8px}
  h2{font-size:15px;margin-top:28px;text-transform:uppercase;letter-spacing:.08em}
  h3{font-size:13.5px;margin:14px 0 4px}
  .meta{color:#666;font-size:12.5px}
  table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
  th,td{border:1px solid #ccc;padding:5px 9px;text-align:left}
  th{background:#f2f2f2}
  ul{margin:6px 0;padding-left:20px}
  li{margin:3px 0}
  .warn{background:#fdf6e3;border-left:3px solid #b58900;padding:8px 12px;
        font-size:12.5px;margin:6px 0}
  .kpis td:first-child{font-weight:bold;width:40%}
  @media print{body{margin:8mm}}
</style></head><body>
<h1>Meridian — scenario report</h1>
<p class="meta">${esc(s.name || target)} · generated ${now} UTC ·
near-real-time signals, daily-resolution flows</p>

<h2>Scenario</h2><p>${esc(n.scenario)}</p>
<h2>What the simulation shows</h2><p>${esc(n.outcome)}</p>

<h2>Headline figures</h2>
<table class="kpis">
<tr><td>Normal throughput in window</td><td>${tons(k.baseline_window_tons)}</td></tr>
<tr><td>Disrupted volume</td><td>${tons(k.blocked_tons)}</td></tr>
<tr><td>Rerouted</td><td>${tons(k.rerouted_tons)} (avg +${days(k.avg_added_days)})</td></tr>
<tr><td>Delayed / undelivered</td><td>${tons(k.delayed_tons)} (${pct(k.delayed_share_of_window * 100)} of normal)</td></tr>
<tr><td>Cargo value delayed</td><td>${usd(k.value_delayed_usd)}</td></tr>
<tr><td>Reroute cost index</td><td>${factor(k.reroute_cost_factor)}</td></tr>
<tr><td>Port congestion dwell</td><td>${factor(k.port_dwell_factor)}</td></tr>
</table>

${classRows ? `<h2>By vessel class</h2>
<table><tr><th>Class</th><th>Capacity cut</th><th>Disrupted</th><th>Delayed</th>
<th>Value delayed</th></tr>${classRows}</table>` : ""}

${exposureRows ? `<h2>Country import exposure</h2>
<table><tr><th>Country</th><th>% of seaborne imports at risk</th></tr>${exposureRows}</table>` : ""}

<h2>Key drivers</h2>
<ul>${n.drivers.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>

<h2>Role-based considerations</h2>
${roleBlocks}

<h2>Assumptions &amp; limitations</h2>
${n.limitations.map((w) => `<div class="warn">${esc(w)}</div>`).join("")}
<p class="meta">Valuation assumptions (USD/ton): ${VESSEL_CLASSES.map((c) =>
    `${CLASS_LABELS[c]} $${result.assumptions.value_per_ton_usd[c]}`).join(" · ")}</p>
</body></html>`;
}

export function downloadReport(result: ScenarioResult, baseline: Baseline): void {
  const html = buildReportHtml(result, baseline);
  const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `meridian_report_${result.scenario.target_chokepoint_id}_${Date.now()}.html`;
  a.click();
  URL.revokeObjectURL(url);
}
