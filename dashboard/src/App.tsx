import { useEffect, useState } from "react";
import { api, Health, RunSummary, Decision, Performance, Logs } from "./api";
import "./App.css";

// ── helpers ──────────────────────────────────────────────────────────────────

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function signedPct(v: number) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

// ── StatusBar ─────────────────────────────────────────────────────────────────

function StatusBar({ health }: { health: Health | null }) {
  if (!health) {
    return <div className="badge badge-red">● API unreachable</div>;
  }
  const daysSince = health.last_run
    ? Math.floor((Date.now() - new Date(health.last_run).getTime()) / 86_400_000)
    : null;
  const stale = daysSince !== null && daysSince > 1;
  return (
    <div className={`badge ${stale ? "badge-yellow" : "badge-green"}`}>
      <span className={`dot ${stale ? "" : "pulse"}`} />
      {stale
        ? `Stale — last run ${daysSince}d ago`
        : `Live — last run ${health.last_run}`}
    </div>
  );
}

// ── PerformanceStrip ──────────────────────────────────────────────────────────

function PerformanceStrip({ data }: { data: Performance | null }) {
  if (!data) return null;
  const verdictLabel =
    data.verdict === "beating_market"
      ? "✓ Beating the market"
      : data.verdict === "better_than_random"
      ? "⚠ Better than random"
      : data.verdict === "worse_than_random"
      ? "✗ Worse than random"
      : null;
  const verdictColor =
    data.verdict === "beating_market"
      ? "#22c55e"
      : data.verdict === "better_than_random"
      ? "#facc15"
      : "#ef4444";

  return (
    <div className="card perf-strip">
      <div className="stat">
        <span className="stat-label">Total runs</span>
        <span className="stat-value">{data.total_runs}</span>
        <span className="stat-sub">{data.total_resolved} resolved</span>
      </div>
      {data.avg_brier !== null ? (
        <>
          <div className="stat">
            <span className="stat-label">Avg Brier</span>
            <span className="stat-value">{data.avg_brier.toFixed(4)}</span>
            <span className="stat-sub">
              Market {data.avg_market_brier?.toFixed(4)} · Random {data.random_baseline}
            </span>
          </div>
          <div className="stat">
            <span className="stat-label">Cumulative return</span>
            <span
              className="stat-value"
              style={{ color: data.cumulative_return >= 0 ? "#22c55e" : "#ef4444" }}
            >
              {signedPct(data.cumulative_return)}
            </span>
          </div>
          {verdictLabel && (
            <div className="stat" style={{ marginLeft: "auto" }}>
              <span className="stat-value" style={{ color: verdictColor, fontSize: 13 }}>
                {verdictLabel}
              </span>
            </div>
          )}
        </>
      ) : (
        <span className="muted" style={{ alignSelf: "center" }}>
          No resolved markets yet — performance will appear once markets close.
        </span>
      )}
    </div>
  );
}

// ── RunsPanel ─────────────────────────────────────────────────────────────────

function RunsPanel({
  runs,
  selected,
  onSelect,
}: {
  runs: RunSummary[];
  selected: string | null;
  onSelect: (d: string) => void;
}) {
  return (
    <div className="card runs-panel">
      <div className="panel-header">
        <span className="panel-title">Run history</span>
        <span className="muted">{runs.length} days</span>
      </div>
      <ul className="run-list">
        {runs.length === 0 && <li className="muted center">No runs yet</li>}
        {runs.map((r) => (
          <li
            key={r.run_date}
            className={`run-item ${r.run_date === selected ? "selected" : ""}`}
            onClick={() => onSelect(r.run_date)}
          >
            <div>
              <div className="run-date">{r.run_date}</div>
              <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                {r.n_decisions} mkts · conf {r.avg_confidence.toFixed(1)}/10
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "var(--accent)", fontFamily: "monospace", fontSize: 11 }}>
                {pct(r.max_edge)}
              </div>
              <div className="muted" style={{ fontSize: 11 }}>max edge</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── DecisionsPanel ────────────────────────────────────────────────────────────

function ConfDots({ v }: { v: number }) {
  return (
    <span className="conf-dots">
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} className={`dot-sm ${i < v ? "active" : ""}`} />
      ))}
    </span>
  );
}

function DecisionsPanel({ decisions, selectedRun }: { decisions: Decision[]; selectedRun: string | null }) {
  return (
    <div className="card decisions-panel">
      <div className="panel-header">
        <span className="panel-title">
          {selectedRun ? `Picks — ${selectedRun}` : "Latest picks"}
        </span>
        <span className="muted">{decisions.length} markets · sorted by edge</span>
      </div>
      {decisions.length === 0 ? (
        <div className="muted center" style={{ padding: "2rem" }}>No decisions found</div>
      ) : (
        <div className="decision-list">
          {decisions.map((d, i) => {
            const edgePos = d.edge >= 0;
            const outcome =
              d.resolved_yes === null ? null : d.resolved_yes ? "YES" : "NO";
            return (
              <div key={d.market_id} className="decision-item">
                <span className="rank">{i + 1}</span>
                <div className="decision-body">
                  <div className="decision-top">
                    <span className="decision-title">{d.title}</span>
                    {outcome !== null && (
                      <span className={`outcome ${outcome === "YES" ? "yes" : "no"}`}>
                        {outcome}
                      </span>
                    )}
                  </div>
                  <div className="decision-meta">
                    <span className={`direction ${d.bet_direction === "YES" ? "yes" : "no"}`}>
                      {d.bet_direction}
                    </span>
                    <span className="mono muted">
                      Mkt {pct(d.market_price)} → Est {pct(d.estimated_prob)}
                    </span>
                    <span className={`edge-badge ${edgePos ? "pos" : "neg"}`}>
                      {signedPct(d.edge)}
                    </span>
                    <span className="muted">ends {d.end_date}</span>
                  </div>
                  <ConfDots v={d.confidence} />
                  {d.rationale && (
                    <p className="rationale">{d.rationale}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── LogsPanel ─────────────────────────────────────────────────────────────────

function LogsPanel({ logs }: { logs: Logs | null }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button className="logs-toggle" onClick={() => setOpen(true)}>
        ▶ Show bot logs {logs ? `(${logs.lines.length} lines)` : ""}
      </button>
    );
  }
  return (
    <div className="card logs-card">
      <div className="panel-header">
        <span className="panel-title" style={{ textTransform: "uppercase", fontSize: 11, letterSpacing: "0.05em", color: "var(--muted)" }}>
          Bot logs
        </span>
        <button className="logs-toggle" onClick={() => setOpen(false)}>Hide</button>
      </div>
      <pre className="logs-pre">
        {logs?.lines.length ? logs.lines.join("\n") : "No logs yet."}
      </pre>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [logs, setLogs] = useState<Logs | null>(null);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Initial load
  useEffect(() => {
    Promise.allSettled([
      api.health().then(setHealth),
      api.runs().then((r) => {
        setRuns(r);
        if (r.length > 0) setSelectedRun(r[0].run_date);
      }),
      api.performance().then(setPerformance),
      api.logs().then(setLogs),
    ]).finally(() => setLoading(false));
  }, []);

  // Load decisions when run changes
  useEffect(() => {
    if (!selectedRun) return;
    api.decisions(selectedRun).then(setDecisions).catch(() => setDecisions([]));
  }, [selectedRun]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <span className="muted">Loading…</span>
      </div>
    );
  }

  return (
    <div className="layout">
      {/* Header */}
      <header className="header">
        <div>
          <h1 className="site-title">PrediBronx</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 12 }}>
            AI-powered Polymarket prediction bot
          </p>
        </div>
        <StatusBar health={health} />
      </header>

      {/* Performance */}
      <PerformanceStrip data={performance} />

      {/* Main grid */}
      <div className="grid">
        <RunsPanel runs={runs} selected={selectedRun} onSelect={setSelectedRun} />
        <DecisionsPanel decisions={decisions} selectedRun={selectedRun} />
      </div>

      {/* Logs */}
      <LogsPanel logs={logs} />
    </div>
  );
}
