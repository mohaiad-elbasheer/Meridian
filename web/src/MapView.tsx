import type { Color, PickingInfo } from "@deck.gl/core";
import { ArcLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import type { FeatureCollection } from "geojson";
import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import worldUrl from "world-atlas/countries-110m.json?url";
import type { Baseline, NetworkNode, ScenarioResult } from "./api";
import { tons } from "./format";

const ACCENT: Color = [232, 163, 61];
const ACCENT_FADE: Color = [232, 163, 61, 70];
const CHOKEPOINT: Color = [127, 142, 163];
const TRANSPARENT: Color = [0, 0, 0, 0];
const PORT: Color = [66, 78, 96];

type Placed = NetworkNode & { lat: number; lon: number };
type Arc = { from: Placed; to: Placed; daily_tons: number; added_days: number };

function hasCoords(n: NetworkNode): n is Placed {
  return typeof n.lat === "number" && typeof n.lon === "number";
}

function tooltip(info: PickingInfo): { text: string } | null {
  const obj = info.object as Placed | Arc | undefined;
  if (!obj) return null;
  if ("daily_tons" in obj) {
    return { text: `reroute via ${obj.to.label ?? obj.to.id}\n${tons(obj.daily_tons)}/day  +${obj.added_days.toFixed(1)} days` };
  }
  const lines = [obj.label ?? obj.id];
  if (obj.baseline_daily_tons) lines.push(`${tons(obj.baseline_daily_tons)}/day baseline`);
  if (obj.baseline_daily_calls) lines.push(`${obj.baseline_daily_calls} calls/day`);
  return { text: lines.join("\n") };
}

// Unwrap rings that cross the antimeridian (Fiji, Chukotka, …) so MapLibre doesn't
// draw full-width horizontal streaks; out-of-range longitudes render on world copies.
function unwrapRing(ring: number[][]): void {
  for (let i = 1; i < ring.length; i++) {
    const prev = ring[i - 1][0];
    if (ring[i][0] - prev > 180) ring[i][0] -= 360;
    else if (prev - ring[i][0] > 180) ring[i][0] += 360;
  }
}

async function loadWorld(): Promise<FeatureCollection> {
  const topo = (await (await fetch(worldUrl)).json()) as Topology;
  const countries = topo.objects.countries as GeometryCollection;
  const fc = feature(topo, countries) as FeatureCollection;
  fc.features = fc.features.filter((f) => f.id !== "010"); // Antarctica: polar ring artifacts
  for (const f of fc.features) {
    const g = f.geometry;
    if (g.type === "Polygon") g.coordinates.forEach(unwrapRing);
    else if (g.type === "MultiPolygon") g.coordinates.forEach((p) => p.forEach(unwrapRing));
  }
  return fc;
}

interface Props {
  baseline: Baseline | null;
  result: ScenarioResult | null;
  targetId: string;
  onSelect: (chokepointId: string) => void;
}

export function MapView({ baseline, result, targetId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const [world, setWorld] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadWorld().then((fc) => {
      if (!cancelled) setWorld(fc);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!container.current || !world) return;
    const map = new maplibregl.Map({
      container: container.current,
      // Inline style over bundled world geometry: no external tile/glyph servers.
      style: {
        version: 8,
        sources: { world: { type: "geojson", data: world } },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#0b0e13" } },
          { id: "land", type: "fill", source: "world", paint: { "fill-color": "#151b25" } },
          {
            id: "borders", type: "line", source: "world",
            paint: { "line-color": "#232d3d", "line-width": 0.6 },
          },
        ],
      },
      center: [45, 16],
      zoom: 1.6,
      attributionControl: false,
    });
    const deckOverlay = new MapboxOverlay({ interleaved: false });
    map.addControl(deckOverlay as unknown as maplibregl.IControl);
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    overlay.current = deckOverlay;
    return () => {
      overlay.current = null;
      map.remove();
    };
  }, [world]);

  useEffect(() => {
    if (!overlay.current || !baseline) return;
    const nodes = baseline.nodes.filter(hasCoords);
    const byId = new Map(nodes.map((n) => [n.id, n]));

    const impacted = result?.impact.chokepoints.find((c) => c.chokepoint_id === targetId);
    const arcs: Arc[] = (impacted?.reroutes ?? []).flatMap((r) => {
      const from = byId.get(targetId);
      const to = byId.get(r.via);
      return from && to ? [{ from, to, daily_tons: r.daily_tons, added_days: r.added_days }] : [];
    });

    overlay.current.setProps({
      getTooltip: tooltip,
      layers: [
        new ScatterplotLayer<Placed>({
          id: "ports",
          data: nodes.filter((n) => n.type === "port"),
          getPosition: (d) => [d.lon, d.lat],
          getRadius: (d) => 9000 + Math.sqrt(d.baseline_daily_calls ?? 1) * 4000,
          radiusMinPixels: 2.5,
          radiusMaxPixels: 7,
          getFillColor: PORT,
          pickable: true,
        }),
        new ScatterplotLayer<Placed>({
          id: "chokepoints",
          data: nodes.filter((n) => n.type === "chokepoint"),
          getPosition: (d) => [d.lon, d.lat],
          getRadius: (d) => 14000 + Math.sqrt(d.baseline_daily_tons ?? 1) * 55,
          radiusMinPixels: 4,
          radiusMaxPixels: 14,
          stroked: true,
          getFillColor: (d) => (d.id === targetId ? ACCENT : CHOKEPOINT),
          getLineColor: (d) => (d.id === targetId ? ACCENT : TRANSPARENT),
          getLineWidth: 2,
          lineWidthUnits: "pixels",
          pickable: true,
          onClick: (info) => {
            const n = info.object as NetworkNode | undefined;
            if (n?.type === "chokepoint") selectRef.current(n.id);
          },
          updateTriggers: { getFillColor: targetId, getLineColor: targetId },
        }),
        new TextLayer<Placed>({
          id: "chokepoint-labels",
          data: nodes.filter((n) => n.type === "chokepoint"),
          getPosition: (d) => [d.lon, d.lat],
          getText: (d) => d.label ?? d.id,
          getSize: 11,
          getColor: [152, 162, 179, 220],
          getPixelOffset: [0, -14],
          fontFamily: "IBM Plex Sans, sans-serif",
          fontWeight: 500,
          outlineWidth: 2,
          outlineColor: [11, 14, 19, 255],
          fontSettings: { sdf: true },
        }),
        new ArcLayer<Arc>({
          id: "reroutes",
          data: arcs,
          getSourcePosition: (d) => [d.from.lon, d.from.lat],
          getTargetPosition: (d) => [d.to.lon, d.to.lat],
          getSourceColor: ACCENT,
          getTargetColor: ACCENT_FADE,
          getWidth: (d) => Math.max(1.5, Math.sqrt(d.daily_tons / 1e5) * 2),
          getHeight: 0.35,
          pickable: true,
        }),
      ],
    });
  }, [baseline, result, targetId, world]);

  return (
    <div className="map-wrap">
      <div ref={container} style={{ position: "absolute", inset: 0 }} />
      <MapLegend hasArcs={Boolean(result)} />
      <div className="map-attrib">
        {result ? "arcs: rerouted flow (width ∝ tons/day)" : "click a chokepoint to target it"}
      </div>
    </div>
  );
}

function MapLegend({ hasArcs }: { hasArcs: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="map-legend">
      <div className="head">
        <span>Maritime chokepoints</span>
        <button aria-label="about this map" onClick={() => setOpen(!open)}>i</button>
      </div>
      <div className="row"><i className="dot cp" /> chokepoint (size ∝ daily tons)</div>
      <div className="row"><i className="dot cp sel" /> selected target</div>
      <div className="row"><i className="dot port" /> major port</div>
      {hasArcs && <div className="row"><i className="arc" /> rerouted flow</div>}
      {open && (
        <div className="legend-info" onClick={() => setOpen(false)}>
          This map focuses on the world&apos;s most important <strong>maritime
          chokepoints</strong> — narrow passages such as the Suez and Panama canals or
          the Straits of Hormuz and Malacca, where a large share of world seaborne
          trade concentrates. IMF PortWatch monitors 28 of them daily; a disruption in
          one ripples into rerouting, longer transit times, freight costs, and
          national import exposure. Click any chokepoint to make it the simulation
          target; hover for its normal traffic.
        </div>
      )}
    </div>
  );
}
