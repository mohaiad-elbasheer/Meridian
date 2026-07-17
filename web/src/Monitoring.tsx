// Monitoring view: the as-is situation. Chokepoint cards with plain-language
// baselines, cargo-mix bars, historical sparklines (live data) with CSV download;
// live signals, trade dependencies (UN Comtrade), and source freshness.

import { useEffect, useState } from "react";
import {
  fetchTimeseries,
  type Baseline, type NetworkNode, type SeriesResponse, type SignalsResponse,
  type SourcesStatus, type TradeDependencies,
} from "./api";
import { ClassMixBar, downloadCsv, Sparkline } from "./charts";
import { pct, tons, usd, worldSharePerDay } from "./format";
import { Signals, Sources } from "./Panel";

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

function ChokepointCard({ node, showSource, onSimulate }: {
  node: NetworkNode;
  showSource: boolean;   // mixed dataset: tag each card with where its baseline came from
  onSimulate: () => void;
}) {
  const [series, setSeries] = useState<SeriesResponse | null>(null);
  useEffect(() => {
    fetchTimeseries(node.id, 90).then(setSeries).catch(() => setSeries(null));
  }, [node.id]);

  const daily = node.baseline_daily_tons ?? 0;
  const points = (series?.points ?? [])
    .filter((p) => p.trade_tons != null)
    .map((p) => ({ date: p.date, value: p.trade_tons as number }));

  return (
    <div className="cp-card">
      <div className="cp-head">
        <span className="cp-name">
          {node.label ?? node.id}
          {showSource && (
            node.baseline_source === "portwatch_daily"
              ? <span className="src-tag observed">PortWatch</span>
              : <span className="src-tag">synthetic</span>
          )}
        </span>
        <button className="cp-sim" onClick={onSimulate}>simulate ▸</button>
      </div>
      <div className="cp-base">
        <span className="mono">{tons(daily)}/day</span> · {node.baseline_daily_calls != null ? Math.round(node.baseline_daily_calls) : "—"}{" "}
        ship transits/day
        <Info title="What is 'normal' here?"
          text={`On a typical day, about ${node.baseline_daily_calls != null ? Math.round(node.baseline_daily_calls) : "—"} ships carrying
          roughly ${tons(daily)} of goods pass through ${node.label ?? node.id} — around
          ${worldSharePerDay(daily)} of all seaborne world trade (approximate; world total
          ≈ 12 billion tons/year). Every disruption result is compared against this
          "normal day" so the numbers have a yardstick.`}
        />
      </div>
      {node.class_shares && <ClassMixBar shares={node.class_shares} />}
      {points.length >= 2 ? (
        <>
          <Sparkline points={points} unit="tons" />
          <div className="cp-actions">
            <button
              className="csv"
              onClick={() =>
                downloadCsv(
                  `${node.id}_daily.csv`,
                  ["date", "transit_calls", "trade_tons"],
                  (series?.points ?? []).map((p) => [p.date, p.transit_calls, p.trade_tons]),
                )
              }
            >
              ⭳ history (CSV)
            </button>
            {series?.illustrative && (
              <span className="illustrative">illustrative series — synthetic demo</span>
            )}
          </div>
        </>
      ) : (
        <div className="cp-noseries">daily history appears once data collection is running</div>
      )}
    </div>
  );
}

function ThroughputRanking({ chokepoints, onSimulate }: {
  chokepoints: NetworkNode[];
  onSimulate: (id: string) => void;
}) {
  const max = Math.max(...chokepoints.map((n) => n.baseline_daily_tons ?? 0), 1);
  return (
    <section className="mon-section">
      <h2>
        Daily throughput ranking
        <Info title="Throughput ranking"
          text="Estimated goods moving through each passage on a normal day, in metric
          tons — with its approximate share of all seaborne world trade. Click a name
          to simulate a disruption there."
        />
      </h2>
      <div className="rank">
        {chokepoints.map((n) => {
          const v = n.baseline_daily_tons ?? 0;
          return (
            <div className="rank-row" key={n.id}>
              <button className="rank-name" onClick={() => onSimulate(n.id)}>
                {n.label ?? n.id}
              </button>
              <div className="rank-track">
                <div className="rank-fill" style={{ width: `${(v / max) * 100}%` }} />
              </div>
              <span className="rank-val">{tons(v)}/d</span>
              <span className="rank-share">{worldSharePerDay(v)} of world trade</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function TradePanel({ trade }: { trade: TradeDependencies | null }) {
  const [reporter, setReporter] = useState<string>("");
  if (!trade?.available || Object.keys(trade.reporters).length === 0) return null;
  const names = Object.keys(trade.reporters).sort();
  const sel = reporter && trade.reporters[reporter] ? reporter : names[0];
  const data = trade.reporters[sel];
  const max = Math.max(...data.partners.map((p) => p.share), 0.001);
  return (
    <section className="mon-section">
      <h2>
        Import dependencies — {trade.source}, {trade.year}
        <Info title="Import dependencies"
          text="Who does each country buy from? Total goods imports by partner, from UN
          Comtrade annual data. This is the data that will replace the curated
          chokepoint-to-country shares used in simulations."
        />
      </h2>
      <div className="field" style={{ maxWidth: 260 }}>
        <select value={sel} onChange={(e) => setReporter(e.target.value)}>
          {names.map((n) => (
            <option key={n} value={n}>{n} — imports {usd(trade.reporters[n].total_import_usd)}</option>
          ))}
        </select>
      </div>
      {data.partners.map((p) => (
        <div className="bar-row" key={p.partner}>
          <span className="iso">{p.partner}</span>
          <div className="track">
            <div className="fill" style={{ width: `${(p.share / max) * 100}%` }} />
          </div>
          <span className="val">{pct(p.share * 100)}</span>
        </div>
      ))}
    </section>
  );
}

interface Props {
  baseline: Baseline | null;
  signals: SignalsResponse | null;
  sources: SourcesStatus | null;
  trade: TradeDependencies | null;
  onApplySignals: (suggested: Record<string, number>) => void;
  onSimulate: (chokepointId: string) => void;
}

export function Monitoring({ baseline, signals, sources, trade, onApplySignals, onSimulate }: Props) {
  const chokepoints = (baseline?.nodes ?? [])
    .filter((n) => n.type === "chokepoint")
    .sort((a, b) => (b.baseline_daily_tons ?? 0) - (a.baseline_daily_tons ?? 0));
  return (
    <div className="monitoring">
      <div>
      <ThroughputRanking chokepoints={chokepoints} onSimulate={onSimulate} />
      <section className="mon-section">
        <h2>
          Chokepoints — current baselines
          <Info title="Why chokepoints?"
            text="A handful of narrow passages concentrate a large share of world seaborne
            trade. Meridian focuses on the most important maritime chokepoints (IMF
            PortWatch monitors 28) because disruptions there ripple into rerouting,
            freight costs, and national import exposure. Cards are ordered by normal
            daily throughput."
          />
        </h2>
        <div className="cp-grid">
          {chokepoints.map((n) => (
            <ChokepointCard key={n.id} node={n}
              showSource={baseline?.provenance === "mixed"}
              onSimulate={() => onSimulate(n.id)} />
          ))}
        </div>
      </section>
      </div>
      <div className="mon-side">
        <Signals signals={signals} onApply={onApplySignals} />
        <TradePanel trade={trade} />
        <Sources status={sources} />
      </div>
    </div>
  );
}
