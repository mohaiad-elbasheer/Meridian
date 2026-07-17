// Advisor narrative generation: deterministic, rule-based interpretation of a
// scenario result. Every sentence is derived from the result's own numbers and
// stated assumptions — nothing is invented. A fine-tuned LLM assist is a later,
// separate layer; this module is the structured foundation it will build on.

import {
  CAUSE_LABELS, CLASS_LABELS, VESSEL_CLASSES,
  type Baseline, type ScenarioResult,
} from "./api";
import { days, factor, pct, shipEquivalents, tons, usd } from "./format";

export type Role = "insurer" | "policy" | "supply_chain";

export const ROLE_LABELS: Record<Role, string> = {
  insurer: "Insurance / risk",
  policy: "Policy maker",
  supply_chain: "Supply-chain manager",
};

export interface Narrative {
  scenario: string;
  outcome: string;
  drivers: string[];
  roleNotes: Record<Role, string[]>;
  limitations: string[];
}

function labelOf(baseline: Baseline, id: string): string {
  return baseline.nodes.find((n) => n.id === id)?.label ?? id;
}

export function buildNarrative(result: ScenarioResult, baseline: Baseline): Narrative {
  const s = result.scenario;
  const k = result.kpis;
  const target = labelOf(baseline, s.target_chokepoint_id);
  const reroutes = result.impact.chokepoints.flatMap((c) => c.reroutes);
  const affected = VESSEL_CLASSES.filter((c) => (k.per_class[c]?.reduction ?? 0) > 0);
  const allClasses = affected.length === VESSEL_CLASSES.length &&
    affected.every((c) => k.per_class[c].reduction === s.capacity_reduction);
  const topCountry = Object.entries(k.top_exposed_countries)[0];
  const severe = k.delayed_share_of_window >= 0.3;

  const scenario =
    `You simulated ${target} losing capacity for ${s.duration_days} days` +
    (allClasses
      ? ` (−${Math.round(s.capacity_reduction * 100)}% across all traffic)`
      : ` (${affected.map((c) => `${CLASS_LABELS[c]} −${Math.round(k.per_class[c].reduction * 100)}%`).join(", ")})`) +
    (s.cause && s.cause !== "unspecified"
      ? `, caused by ${CAUSE_LABELS[s.cause].toLowerCase()}. The cause automatically raised the related risk conditions (${Object.keys(result.auto_clamps).filter((c) => c !== "chokepoint_disruption").join(", ") || "none"}).`
      : ". No cause was specified, so only the disruption itself drives the risk conditions.");

  const outcome =
    `Over the ${s.duration_days}-day window, ${tons(k.blocked_tons)} that would normally ` +
    `pass through ${target} is disrupted (${pct(k.delayed_share_of_window * 100 + (k.rerouted_tons / Math.max(k.baseline_window_tons, 1)) * 100)} of its normal throughput). ` +
    (reroutes.length > 0
      ? `${tons(k.rerouted_tons)} finds an alternative route (${[...new Set(reroutes.map((r) => labelOf(baseline, r.via)))].join(", ")}), arriving on average ${days(k.avg_added_days)} late. The remaining ${tons(k.delayed_tons)} (${shipEquivalents(k.delayed_tons)}) cannot move within the window. `
      : `No alternative route exists in the network, so the entire ${tons(k.delayed_tons)} (${shipEquivalents(k.delayed_tons)}) is delayed. `) +
    `At the stated cargo-value assumptions this puts ${usd(k.value_delayed_usd)} of goods behind schedule.`;

  const drivers: string[] = [];
  drivers.push(
    `Capacity cut at ${target} is the primary driver: −${Math.round((1 - (result.network_multipliers[`chokepoint_capacity_multiplier:${s.target_chokepoint_id}`] ?? 1)) * 100)}% effective capacity.`);
  if (reroutes.length > 0) {
    drivers.push(
      `Alternative-route slack caps rerouting: beyond it, volume waits. Reroute detour adds ${days(k.avg_added_days)} on average.`);
  } else {
    drivers.push("Absence of an alternative route makes this chokepoint an outright bottleneck — nothing reroutes.");
  }
  if (k.reroute_cost_factor > 1.05) {
    drivers.push(
      `Soft factors raise the reroute cost index to ${factor(k.reroute_cost_factor)} (war-risk/escalation conditions), a cost amplifier on every rerouted ton.`);
  }
  if (k.port_dwell_factor > 1.05) {
    drivers.push(
      `Congestion at receiving routes adds dwell (${factor(k.port_dwell_factor)} on baseline handling time).`);
  }
  if (topCountry) {
    drivers.push(
      `Import exposure concentrates in ${topCountry[0]} (${pct(topCountry[1])} of its seaborne imports at risk).`);
  }

  const exposedList = Object.entries(k.top_exposed_countries).slice(0, 3)
    .map(([c, v]) => `${c} (${pct(v)})`).join(", ");

  const roleNotes: Record<Role, string[]> = {
    insurer: [
      `First-order exposure: ${usd(k.value_delayed_usd)} of cargo delayed and ${usd(k.value_rerouted_usd)} rerouted — review delay/demurrage and war-risk lines against these magnitudes.`,
      k.reroute_cost_factor > 1.05
        ? `War-risk conditions are elevated (${factor(k.reroute_cost_factor)} reroute cost index) — premium adequacy on affected routes is the immediate question.`
        : "Soft-factor indices stayed near baseline — this scenario stresses volumes more than risk pricing.",
      `Tail to watch: if the disruption outlasts the ${s.duration_days}-day window, delayed volume compounds roughly linearly (~${tons(k.delayed_tons / s.duration_days)}/day).`,
    ],
    policy: [
      topCountry
        ? `Most exposed trading partners: ${exposedList}. These are the capitals that feel this scenario first.`
        : "No country exposure is recorded for this chokepoint in the current network.",
      reroutes.length > 0
        ? `Reroute capacity exists but is finite — supporting throughput at ${[...new Set(reroutes.map((r) => labelOf(baseline, r.via)))].join(", ")} is the highest-leverage mitigation.`
        : "With no maritime alternative, mitigation is demand-side: strategic reserves, overland substitution, or demand deferral.",
      severe
        ? `At ${pct(k.delayed_share_of_window * 100)} of normal throughput undelivered, essential-goods screening for import-dependent partners is warranted.`
        : "Undelivered share stays below typical buffer-stock coverage; monitor rather than intervene.",
    ],
    supply_chain: [
      `Plan for +${days(k.avg_added_days)} on rerouted lanes${reroutes.length ? "" : " — none available here; treat all volume through this passage as delayed"}; add it to contracted lead times now.`,
      affected.length < VESSEL_CLASSES.length
        ? `Only ${affected.map((c) => CLASS_LABELS[c]).join(", ")} traffic is hit — shift what you can to unaffected vessel classes or routings.`
        : "All cargo classes are affected — class-switching offers no relief in this scenario.",
      `Inventory math: the window holds back ${tons(k.delayed_tons)}; compare against your safety stock in affected categories (${affected.map((c) => CLASS_LABELS[c]).join(", ") || "all"}).`,
    ],
  };

  const limitations = [
    ...result.warnings,
    "Interpretation is generated by deterministic rules from this run's numbers — no forecasting model or AI is involved at this stage.",
  ];

  return { scenario, outcome, drivers, roleNotes, limitations };
}
