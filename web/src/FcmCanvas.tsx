// Causal-map view: the macro FCM rendered as a layered graph. Analysts set scenario
// clamps by clicking a concept; edge WEIGHTS are literature-governed and not editable
// here (provenance rules, CLAUDE.md §2) — provisional edges render dashed.

import {
  Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";
import { fetchFcmMap, type FcmMap } from "./api";

const LAYER_ORDER = ["hazard", "logistics", "economic", "outcome"] as const;
const LAYER_LABELS: Record<string, string> = {
  hazard: "Hazards", logistics: "Logistics", economic: "Economic", outcome: "Outcomes",
};

type ConceptData = { label: string; layer: string; clamp: number | undefined };
type ConceptNode = Node<ConceptData, "concept">;

function ConceptNodeView({ data, selected }: NodeProps<ConceptNode>) {
  const clamped = data.clamp !== undefined;
  return (
    <div className={`fcm-node${clamped ? " clamped" : ""}${selected ? " selected" : ""}`}>
      <Handle type="target" position={Position.Left} className="fcm-handle" />
      <span className="fcm-layer">{data.layer}</span>
      <span className="fcm-label">{data.label}</span>
      {clamped && <span className="fcm-clamp">⊦ {data.clamp!.toFixed(2)}</span>}
      <Handle type="source" position={Position.Right} className="fcm-handle" />
    </div>
  );
}

const nodeTypes = { concept: ConceptNodeView };

interface Props {
  clamps: Record<string, number>;
  onClampsChange: (clamps: Record<string, number>) => void;
}

export function FcmCanvas({ clamps, onClampsChange }: Props) {
  const [fcm, setFcm] = useState<FcmMap | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetchFcmMap().then(setFcm).catch(() => setFcm(null));
  }, []);

  const nodes: ConceptNode[] = useMemo(() => {
    if (!fcm) return [];
    const byLayer = new Map<string, string[]>();
    for (const c of fcm.concepts) {
      byLayer.set(c.layer, [...(byLayer.get(c.layer) ?? []), c.id]);
    }
    return fcm.concepts.map((c) => {
      const col = LAYER_ORDER.indexOf(c.layer as (typeof LAYER_ORDER)[number]);
      const row = (byLayer.get(c.layer) ?? []).indexOf(c.id);
      return {
        id: c.id,
        type: "concept" as const,
        position: { x: col * 260, y: row * 96 + (col % 2) * 34 },
        data: { label: c.label, layer: LAYER_LABELS[c.layer] ?? c.layer, clamp: clamps[c.id] },
      };
    });
  }, [fcm, clamps]);

  const edges: Edge[] = useMemo(
    () =>
      (fcm?.edges ?? []).map((e) => ({
        id: `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        label: (e.weight > 0 ? "+" : "") + e.weight.toFixed(1),
        className: `fcm-edge ${e.weight >= 0 ? "pos" : "neg"}`,
        style: e.provenance.provisional ? { strokeDasharray: "5 4" } : undefined,
        animated: false,
      })),
    [fcm],
  );

  function setClamp(id: string, value: number | undefined) {
    const next = { ...clamps };
    if (value === undefined) delete next[id];
    else next[id] = value;
    onClampsChange(next);
  }

  const selectedConcept = fcm?.concepts.find((c) => c.id === selected);
  return (
    <div className="map-wrap fcm-wrap">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, n) => setSelected(n.id)}
        onPaneClick={() => setSelected(null)}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
        fitView
        proOptions={{ hideAttribution: true }}
        colorMode="dark"
      >
        <Background gap={24} size={1} />
      </ReactFlow>
      {selectedConcept && (
        <div className="fcm-editor">
          <div className="fcm-editor-title">{selectedConcept.label}</div>
          <label>
            clamp activation{" "}
            <span className="value">{(clamps[selectedConcept.id] ?? 0).toFixed(2)}</span>
          </label>
          <input
            type="range" min={-100} max={100} step={5}
            value={Math.round((clamps[selectedConcept.id] ?? 0) * 100)}
            onChange={(e) => setClamp(selectedConcept.id, Number(e.target.value) / 100)}
          />
          <div className="fcm-editor-row">
            <button onClick={() => setClamp(selectedConcept.id, undefined)}>release</button>
            <button onClick={() => setSelected(null)}>close</button>
          </div>
        </div>
      )}
      <div className="map-attrib">
        weights are literature-governed (dashed = provisional) — click a concept to
        clamp it in the scenario
      </div>
    </div>
  );
}
