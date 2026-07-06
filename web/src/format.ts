// Number formatting: always with units, mono-friendly, no false precision.

export function tons(value: number): string {
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)} Mt`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)} kt`;
  return `${Math.round(value)} t`;
}

export function days(value: number): string {
  return `${value.toFixed(1)} d`;
}

export function pct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function factor(value: number): string {
  return `×${value.toFixed(2)}`;
}

// World seaborne trade ≈ 12 billion tons/year (UNCTAD order of magnitude) — used
// only for relatable comparisons, always phrased as approximate.
const WORLD_SEABORNE_TONS_PER_YEAR = 12e9;
// A large (Capesize/Panamax-class) bulk carrier cargo, order of magnitude.
const LARGE_SHIP_TONS = 70_000;

export function worldSharePerDay(tonsPerDay: number): string {
  return `${((tonsPerDay * 365) / WORLD_SEABORNE_TONS_PER_YEAR * 100).toFixed(1)}%`;
}

export function shipEquivalents(tonsTotal: number): string {
  const n = Math.round(tonsTotal / LARGE_SHIP_TONS);
  return n >= 1 ? `≈ ${n.toLocaleString()} large ship cargoes` : "< 1 large ship cargo";
}

export function usd(value: number): string {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)} B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)} M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)} k`;
  return `$${Math.round(value)}`;
}
