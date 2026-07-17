// Contract test for QC REL-04: save -> load -> rebuild must produce an equivalent
// ScenarioSpec (name excluded — it is display-only and regenerated).

import { describe, expect, it } from "vitest";
import type { ScenarioSpec } from "./api";
import { builderFromSpec, buildSpec, initialBuilderValues } from "./Builder";

const CLAMPS = { armed_conflict: 1.0 };

function normalized(spec: ScenarioSpec) {
  const { name: _name, ...rest } = spec;
  return rest;
}

function roundtrip(spec: ScenarioSpec): ScenarioSpec {
  const builder = builderFromSpec(spec, initialBuilderValues("suez_canal"));
  return buildSpec(builder, Object.fromEntries(
    (spec.fcm_clamps ?? []).map((c) => [c.concept_id, c.value])));
}

describe("scenario save/load round-trip", () => {
  it("guided uniform scenario", () => {
    const spec = buildSpec(
      { ...initialBuilderValues("suez_canal"), severity: 0.6, duration: 21, cause: "conflict" },
      CLAMPS,
    );
    expect(normalized(roundtrip(spec))).toEqual(normalized(spec));
  });

  it("guided scenario with disabled classes", () => {
    const v = initialBuilderValues("strait_of_hormuz");
    v.enabled = { ...v.enabled, container: false, dry_bulk: false };
    v.severity = 0.9;
    const spec = buildSpec(v, {});
    expect(spec.class_reductions).toBeDefined();
    expect(normalized(roundtrip(spec))).toEqual(normalized(spec));
  });

  it("expert scenario with distinct per-class reductions and custom valuations", () => {
    const v = initialBuilderValues("strait_of_malacca");
    v.expert = true;
    v.classReductions = {
      container: 0.9, dry_bulk: 0.2, general_cargo: 0.5, roro: 0.0, tanker: 0.35,
    };
    v.valuePerTon = { ...v.valuePerTon, tanker: 700, container: 5200 };
    v.duration = 45;
    v.cause = "policy";
    const spec = buildSpec(v, { sanction_risk: 0.95 });
    const back = roundtrip(spec);
    expect(normalized(back)).toEqual(normalized(spec));
    // loading an expert spec must land in expert mode (REL-04 root cause)
    expect(builderFromSpec(spec, initialBuilderValues("suez_canal")).expert).toBe(true);
  });
});
