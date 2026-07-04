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
