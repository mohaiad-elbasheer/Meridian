// In-browser port of the Meridian engine for the STATIC DEMO build only.
// This is not the research engine: engine/meridian_engine (Python) is authoritative.
// A parity test (engine.parity.test.ts) checks this port against results computed by
// the Python engine — if you change the Python engine, regenerate the fixtures with
// `python tools/gen_demo_data.py` and keep this file in sync.

import type { Baseline, Clamp, FcmMap, NetworkNode, ScenarioResult, ScenarioSpec } from "../api";

export interface FcmSpecFull extends FcmMap {
  squashing: "sigmoid" | "tanh";
  lam: number;
  couplings: {
    concept_id: string;
    network_parameter: string;
    gain: number;
    min_multiplier: number;
    max_multiplier: number;
  }[];
  concepts: (FcmMap["concepts"][number] & { initial_activation?: number })[];
}

const BASELINE_PORT_DWELL_DAYS = 1.5;
const CAPACITY_KEY = "chokepoint_capacity_multiplier";
const DISRUPTION_CONCEPT = "chokepoint_disruption";

const VESSEL_CLASSES = ["container", "dry_bulk", "general_cargo", "roro", "tanker"] as const;

const DEFAULT_VALUE_PER_TON_USD: Record<string, number> = {
  container: 4000, dry_bulk: 120, general_cargo: 900, roro: 3000, tanker: 550,
};

const DEFAULT_CLASS_SHARES: Record<string, number> = {
  container: 0.3, dry_bulk: 0.25, general_cargo: 0.15, roro: 0.05, tanker: 0.25,
};

// cause -> [concept, base, gain]: clamp = clip(base + gain * severity, 0, 1)
const CAUSE_CLAMP_RULES: Record<string, [string, number, number][]> = {
  conflict: [["armed_conflict", 0.3, 0.7]],
  natural_hazard: [["natural_hazard", 0.3, 0.7]],
  policy: [["sanction_risk", 0.3, 0.7]],
  accident: [],
  unspecified: [],
};

function round6(x: number): number {
  return Math.round(x * 1e6) / 1e6;
}

interface FcmResult {
  converged: boolean;
  steps: number;
  final_activations: Record<string, number>;
  trajectories: Record<string, number[]>;
  network_multipliers: Record<string, number>;
  provisional_edges_used: number;
}

function squash(x: number, kind: "sigmoid" | "tanh", lam: number): number {
  return kind === "sigmoid" ? 1 / (1 + Math.exp(-lam * x)) : Math.tanh(lam * x);
}

export function simulateFcm(
  spec: FcmSpecFull,
  clamps: Clamp[],
  maxSteps = 100,
  epsilon = 1e-4,
): FcmResult {
  const ids = spec.concepts.map((c) => c.id);
  const index = new Map(ids.map((id, i) => [id, i]));
  for (const c of clamps) {
    if (!index.has(c.concept_id)) throw new Error(`Clamp references unknown concept: ${c.concept_id}`);
  }
  const n = ids.length;
  const w: number[][] = Array.from({ length: n }, () => Array<number>(n).fill(0));
  for (const e of spec.edges) w[index.get(e.source)!][index.get(e.target)!] = e.weight;

  const applyClamps = (a: number[], step: number) => {
    for (const c of clamps) {
      const from = c.from_step ?? 0;
      const to = c.to_step ?? null;
      if (step >= from && (to === null || step <= to)) a[index.get(c.concept_id)!] = c.value;
    }
  };

  let a = spec.concepts.map((c) => c.initial_activation ?? 0);
  applyClamps(a, 0);
  const trajectories: number[][] = [a.slice()];

  let converged = false;
  let step = 0;
  for (step = 1; step <= maxSteps; step++) {
    const next = a.map((_, j) => {
      let acc = a[j];
      for (let i = 0; i < n; i++) acc += a[i] * w[i][j];
      return squash(acc, spec.squashing, spec.lam);
    });
    applyClamps(next, step);
    trajectories.push(next.slice());
    const delta = Math.max(...next.map((v, i) => Math.abs(v - a[i])));
    a = next;
    if (delta < epsilon) {
      converged = true;
      break;
    }
  }

  const final: Record<string, number> = {};
  ids.forEach((id, i) => (final[id] = a[i]));
  const multipliers: Record<string, number> = {};
  for (const cpl of spec.couplings) {
    const m = 1 + cpl.gain * final[cpl.concept_id];
    multipliers[cpl.network_parameter] = Math.min(
      cpl.max_multiplier, Math.max(cpl.min_multiplier, m),
    );
  }
  return {
    converged,
    steps: step,
    final_activations: final,
    trajectories: Object.fromEntries(ids.map((id, i) => [id, trajectories.map((t) => t[i])])),
    network_multipliers: multipliers,
    provisional_edges_used: spec.edges.filter((e) => e.provenance.provisional).length,
  };
}

interface NetworkImpact {
  rerouted_tons: number;
  delayed_tons: number;
  avg_added_days: number;
  country_exposure: Record<string, number>;
  chokepoints: {
    chokepoint_id: string;
    capacity_multiplier: number;
    baseline_daily_tons: number;
    blocked_tons: number;
    rerouted_tons: number;
    delayed_tons: number;
    reroutes: { via: string; daily_tons: number; added_days: number }[];
  }[];
}

function capacityMultiplier(multipliers: Record<string, number>, nodeId: string): number {
  return multipliers[`${CAPACITY_KEY}:${nodeId}`] ?? 1.0;
}

export function applyScenario(
  baseline: Baseline,
  multipliers: Record<string, number>,
  durationDays: number,
): NetworkImpact {
  const dwellFactor = multipliers["port_dwell_factor"] ?? 1.0;
  const dwellAdded = Math.max(0, dwellFactor - 1) * BASELINE_PORT_DWELL_DAYS;
  const nodes = new Map<string, NetworkNode>(baseline.nodes.map((n) => [n.id, n]));

  const impact: NetworkImpact = {
    rerouted_tons: 0, delayed_tons: 0, avg_added_days: 0,
    country_exposure: {}, chokepoints: [],
  };
  let reroutedDayTons = 0;

  for (const node of baseline.nodes) {
    if (node.type !== "chokepoint") continue;
    const m = capacityMultiplier(multipliers, node.id);
    if (m >= 1.0) continue;
    const blockedDaily = (node.baseline_daily_tons ?? 0) * (1 - m);
    let remaining = blockedDaily;
    const reroutes: NetworkImpact["chokepoints"][number]["reroutes"] = [];
    const alts = baseline.edges
      .filter((e) => e.source === node.id && e.kind === "alt_route")
      .sort((a, b) => (a.added_days ?? 0) - (b.added_days ?? 0));
    for (const edge of alts) {
      if (remaining <= 0) break;
      const alt = nodes.get(edge.target)!;
      const altAvailable = (alt.capacity_daily_tons ?? 0) * capacityMultiplier(multipliers, alt.id);
      const slackDaily = Math.max(0, altAvailable - (alt.baseline_daily_tons ?? 0));
      const take = Math.min(remaining, slackDaily);
      if (take > 0) {
        const added = (edge.added_days ?? 0) + dwellAdded;
        reroutedDayTons += take * durationDays * added;
        reroutes.push({ via: alt.id, daily_tons: take, added_days: added });
        remaining -= take;
      }
    }
    const reroutedDaily = blockedDaily - remaining;
    for (const edge of baseline.edges) {
      if (edge.source !== node.id || edge.kind !== "import_share") continue;
      const exposure = (edge.share ?? 0) * (1 - m) * 100;
      impact.country_exposure[edge.target] = Math.min(
        100, (impact.country_exposure[edge.target] ?? 0) + exposure,
      );
    }
    impact.rerouted_tons += reroutedDaily * durationDays;
    impact.delayed_tons += remaining * durationDays;
    impact.chokepoints.push({
      chokepoint_id: node.id,
      capacity_multiplier: m,
      baseline_daily_tons: node.baseline_daily_tons ?? 0,
      blocked_tons: blockedDaily * durationDays,
      rerouted_tons: reroutedDaily * durationDays,
      delayed_tons: remaining * durationDays,
      reroutes,
    });
  }
  if (impact.rerouted_tons > 0) impact.avg_added_days = reroutedDayTons / impact.rerouted_tons;
  impact.country_exposure = Object.fromEntries(
    Object.entries(impact.country_exposure).sort((a, b) => b[1] - a[1]),
  );
  return impact;
}

export function runScenario(
  fcmSpec: FcmSpecFull,
  baseline: Baseline,
  scenario: ScenarioSpec,
): ScenarioResult {
  const node = baseline.nodes.find((n) => n.id === scenario.target_chokepoint_id);
  if (!node || node.type !== "chokepoint") {
    throw new Error(`Unknown chokepoint: ${scenario.target_chokepoint_id}`);
  }

  const baselineDaily = node.baseline_daily_tons ?? 0;
  const sharesProvisional = node.class_shares == null;
  const shares = node.class_shares ?? DEFAULT_CLASS_SHARES;

  const reductions: Record<string, number> = {};
  const blockedDailyByClass: Record<string, number> = {};
  let blockedDaily = 0;
  for (const c of VESSEL_CLASSES) {
    reductions[c] = scenario.class_reductions?.[c] ?? scenario.capacity_reduction;
    blockedDailyByClass[c] = baselineDaily * (shares[c] ?? 0) * reductions[c];
    blockedDaily += blockedDailyByClass[c];
  }
  const effectiveReduction = baselineDaily > 0 ? blockedDaily / baselineDaily : 0;

  // Dynamic soft factors: scenario definition drives the FCM; expert clamps win.
  const auto: Record<string, number> = { [DISRUPTION_CONCEPT]: round6(effectiveReduction) };
  for (const [concept, base, gain] of CAUSE_CLAMP_RULES[scenario.cause ?? "unspecified"]) {
    auto[concept] = round6(Math.min(1, base + gain * effectiveReduction));
  }
  const expertConcepts = new Set((scenario.fcm_clamps ?? []).map((c) => c.concept_id));
  const clamps: Clamp[] = [
    ...(scenario.fcm_clamps ?? []),
    ...Object.entries(auto)
      .filter(([k]) => !expertConcepts.has(k))
      .map(([concept_id, value]) => ({ concept_id, value })),
  ];
  const fcm = simulateFcm(fcmSpec, clamps);

  const applied: Record<string, number> = {
    [`${CAPACITY_KEY}:${scenario.target_chokepoint_id}`]: 1 - effectiveReduction,
  };
  for (const key of ["port_dwell_factor", "reroute_cost_factor"]) {
    if (key in fcm.network_multipliers) applied[key] = fcm.network_multipliers[key];
  }
  const impact = applyScenario(baseline, applied, scenario.duration_days);

  const values = { ...DEFAULT_VALUE_PER_TON_USD, ...(scenario.value_per_ton_usd ?? {}) };
  const perClass: ScenarioResult["kpis"]["per_class"] = {};
  let valueDelayed = 0;
  let valueRerouted = 0;
  for (const c of VESSEL_CLASSES) {
    const frac = blockedDaily > 0 ? blockedDailyByClass[c] / blockedDaily : 0;
    const blockedC = blockedDailyByClass[c] * scenario.duration_days;
    const reroutedC = impact.rerouted_tons * frac;
    const delayedC = impact.delayed_tons * frac;
    const vDelayed = delayedC * values[c];
    valueDelayed += vDelayed;
    valueRerouted += reroutedC * values[c];
    perClass[c] = {
      share: shares[c] ?? 0, reduction: reductions[c], blocked_tons: blockedC,
      rerouted_tons: reroutedC, delayed_tons: delayedC, value_delayed_usd: vDelayed,
    };
  }

  const windowTons = baselineDaily * scenario.duration_days;
  const kpis: ScenarioResult["kpis"] = {
    baseline_window_tons: windowTons,
    blocked_tons: blockedDaily * scenario.duration_days,
    rerouted_tons: impact.rerouted_tons,
    delayed_tons: impact.delayed_tons,
    delayed_share_of_window: windowTons > 0 ? impact.delayed_tons / windowTons : 0,
    avg_added_days: impact.avg_added_days,
    value_delayed_usd: valueDelayed,
    value_rerouted_usd: valueRerouted,
    per_class: perClass,
    reroute_cost_factor: applied["reroute_cost_factor"] ?? 1,
    port_dwell_factor: applied["port_dwell_factor"] ?? 1,
    landed_cost_activation: fcm.final_activations["landed_cost"] ?? 0,
    supply_availability_activation: fcm.final_activations["supply_availability"] ?? 0,
    top_exposed_countries: Object.fromEntries(
      Object.entries(impact.country_exposure).slice(0, 8)),
  };

  const causeRules = CAUSE_CLAMP_RULES[scenario.cause ?? "unspecified"];
  const assumptions: ScenarioResult["assumptions"] = {
    value_per_ton_usd: values,
    value_per_ton_provisional: true,
    class_shares: shares,
    class_shares_source: sharesProvisional ? "default_provisional" : "curated_seed",
    ...{ cause_clamp_rules: Object.fromEntries(
      causeRules.map(([c, base, gain]) => [c, { base, gain }])) },
  };

  const provisional = fcmSpec.edges.filter((e) => e.provenance.provisional).length;
  const warnings: string[] = [];
  if (provisional > 0) {
    warnings.push(
      `${provisional}/${fcmSpec.edges.length} FCM edge weights are provisional ` +
        "(citation unassigned) — treat soft-factor outputs as indicative",
    );
  }
  if (baseline.synthetic) {
    warnings.push(
      `baselines: ${baseline.source} — synthetic development seed, not PortWatch data`,
    );
  }
  warnings.push(...(baseline.data_warnings ?? []));
  warnings.push(
    "monetary figures use provisional USD/ton assumptions (see assumptions) — " +
      "adjust them to your book of business",
  );

  return {
    scenario,
    fcm: {
      converged: fcm.converged,
      steps: fcm.steps,
      final_activations: fcm.final_activations,
      network_multipliers: fcm.network_multipliers,
    },
    auto_clamps: auto,
    network_multipliers: applied,
    impact,
    kpis,
    assumptions,
    provisional_edges: provisional,
    total_edges: fcmSpec.edges.length,
    warnings,
  };
}
