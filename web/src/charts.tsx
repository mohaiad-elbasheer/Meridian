// Small hand-rolled SVG charts: one accent hue for magnitude, 2px surface gaps
// between stacked segments, direct labels — no charting dependency.

import { useState } from "react";
import { CLASS_LABELS, VESSEL_CLASSES, type VesselClass } from "./api";
import { tons } from "./format";

// Categorical palette for vessel classes (identity encoding). Validated for the
// dark surface with the palette validator: lightness band, chroma, contrast >= 3:1
// all PASS; adjacent-pair CVD separation sits in the floor band, which is legal
// here because every use ships direct labels (legend / row labels) alongside color.
// Fixed class->hue assignment — never reordered or cycled.
export const CLASS_COLORS: Record<VesselClass, string> = {
  container: "#3987e5",      // blue
  dry_bulk: "#199e70",       // aqua
  general_cargo: "#c98500",  // yellow
  roro: "#008300",           // green
  tanker: "#9085e9",         // violet
};

export function ClassMixBar({ shares }: { shares: Record<string, number> }) {
  let x = 0;
  const width = 100;
  return (
    <div className="classmix">
      <svg viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden>
        {VESSEL_CLASSES.map((c) => {
          const w = (shares[c] ?? 0) * width;
          const seg = (
            <rect key={c} x={x} y={0} width={Math.max(0, w - 0.8)} height={8} rx={1}
              fill={CLASS_COLORS[c]} />
          );
          x += w;
          return seg;
        })}
      </svg>
      <div className="classmix-legend">
        {VESSEL_CLASSES.filter((c) => (shares[c] ?? 0) >= 0.03).map((c) => (
          <span key={c}>
            <i className="sw" style={{ background: CLASS_COLORS[c] }} />
            {CLASS_LABELS[c]} {Math.round((shares[c] ?? 0) * 100)}%
          </span>
        ))}
      </div>
    </div>
  );
}

export interface SparkPoint {
  date: string;
  value: number;
}

export function Sparkline({ points, unit, height = 56 }: {
  points: SparkPoint[];
  unit: "tons" | "calls";
  height?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (points.length < 2) return null;
  const w = 260;
  const h = height;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const xAt = (i: number) => (i / (points.length - 1)) * w;
  const yAt = (v: number) => h - 4 - ((v - min) / span) * (h - 10);
  const path = points.map((p, i) => `${i ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(p.value).toFixed(1)}`).join(" ");
  const area = `${path} L${w},${h} L0,${h} Z`;
  const hi = hover !== null ? Math.max(0, Math.min(points.length - 1, hover)) : null;
  return (
    <div className="spark" style={{ ["--spark-h" as string]: `${h}px` }}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        onMouseMove={(e) => {
          const rect = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
          setHover(Math.round(((e.clientX - rect.left) / rect.width) * (points.length - 1)));
        }}
        onMouseLeave={() => setHover(null)}
      >
        <path d={area} fill="var(--accent)" opacity={0.1} />
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth={1.6}
          vectorEffect="non-scaling-stroke" />
        {hi !== null && (
          <>
            <line x1={xAt(hi)} x2={xAt(hi)} y1={0} y2={h} stroke="var(--ink-3)" strokeWidth={0.6} />
            <circle cx={xAt(hi)} cy={yAt(points[hi].value)} r={2.6} fill="var(--accent)" />
          </>
        )}
      </svg>
      <div className="spark-caption">
        {hi !== null ? (
          <>
            <span className="mono">{points[hi].date}</span>{" "}
            <span className="mono">
              {unit === "tons" ? tons(points[hi].value) : `${Math.round(points[hi].value)} calls`}
            </span>
          </>
        ) : (
          <>
            {points[0].date} → {points[points.length - 1].date} · min{" "}
            {unit === "tons" ? tons(min) : Math.round(min)} · max{" "}
            {unit === "tons" ? tons(max) : Math.round(max)}
          </>
        )}
      </div>
    </div>
  );
}

export function downloadCsv(filename: string, header: string[], rows: (string | number | null)[][]) {
  const body = [header.join(","), ...rows.map((r) => r.map((v) => v ?? "").join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([body], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
