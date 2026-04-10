import { useEffect, useState, Fragment } from "react";
import { api, Health, RunSummary, Decision, Performance, Logs } from "./api";
import "./App.css";

// ── Helpers ───────────────────────────────────────────────────────────────

const pct = (v: number, decimals = 1) =>
  `${(v * 100).toFixed(decimals)}%`;

const signedPct = (v: number, decimals = 1) =>
  `${v >= 0 ? "+" : ""}${(v * 100).toFixed(decimals)}%`;

// ── StatusPill ────────────────────────────────────────────────────────────

function StatusPill({ health }: { health: Health | null }) {
  if (!health)
    return <div className="status-pill error"><span className="status-dot" />API unreachable</div>;

  const days = health.last_run
    ? Math.floor((Date.now() - new Date(health.last_run).getTime()) / 86_400_000)
    : null;
  const stale = days !== null && days > 1;

  return (
    <div className={`status-pill ${stale ? "stale" : "live"}`}>
      <span className={`status-dot ${stale ? "" : "pulse"}`} />
      {stale ? `Stale — last run ${days}d ago` : `Live — last run ${health.last_run}`}
    </div>
  );
}

// ── StatsBar ──────────────────────────────────────────────────────────────

function StatsBar({ data }: { data: Performance | null }) {
  if (!data) return <div className="stats-bar" />;

  const returnColor =
    data.cumulative_return > 0 ? "green" : data.cumulative_return < 0 ? "red" : "";

  const verdictLabel =
    data.verdict === "beating_market" ? "↑ Beating market" :
    data.verdict === "better_than_random" ? "~ Better than random" :
    data.verdict === "worse_than_random" ? "↓ Worse than random" : null;

  const verdictClass =
    data.verdict === "beating_market" ? "good" :
    data.verdict === "better_than_random" ? "mid" : "bad";

  return (
    <div className="stats-bar">
      <div className="stat-cell">
        <span className="stat-label">Total runs</span>
        <span className="stat-value">{data.total_runs}</span>
        <span className="stat-sub">{data.total_resolved} resolved</span>
      </div>
      <div className="stat-cell">
        <span className="stat-label">Avg Brier score</span>
        <span className={`stat-value ${data.avg_brier !== null && data.avg_market_brier !== null && data.avg_brier < data.avg_market_brier ? "green" : ""}`}>
          {data.avg_brier?.toFixed(4) ?? "—"}
        </span>
        <span className="stat-sub">
          Market {data.avg_market_brier?.toFixed(4)} · Random {data.random_baseline}
        </span>
      </div>
      <div className="stat-cell">
        <span className="stat-label">Paper return</span>
        <span className={`stat-value ${returnColor}`}>
          {signedPct(data.cumulative_return)}
        </span>
        <span className="stat-sub">since inception</span>
      </div>
      {verdictLabel && (
        <div className="stat-cell">
          <span className="stat-label">Verdict</span>
          <span className={`verdict-badge ${verdictClass}`}>{verdictLabel}</span>
        </div>
      )}
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────

function Sidebar({
  runs,
  selected,
  onSelect,
}: {
  runs: RunSummary[];
  selected: string | null;
  onSelect: (d: string) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Run history — {runs.length} days</span>
      </div>
      <ul className="run-list">
        {runs.length === 0 && (
          <li style={{ padding: "16px 14px", color: "#C4BDB7", fontSize: 12 }}>No runs yet</li>
        )}
        {runs.map((r) => (
          <li
            key={r.run_date}
            className={`run-item ${r.run_date === selected ? "active" : ""}`}
            onClick={() => onSelect(r.run_date)}
          >
            <div>
              <div className="run-date">{r.run_date}</div>
              <div className="run-meta">
                {r.n_decisions} mkts · {r.avg_confidence.toFixed(1)}/10 conf
              </div>
            </div>
            <div className="run-edge">{pct(r.avg_edge)}</div>
          </li>
        ))}
      </ul>
    </aside>
  );
}

// ── Decision row ──────────────────────────────────────────────────────────

function DecisionRow({ d, i }: { d: Decision; i: number }) {
  const [open, setOpen] = useState(false);
  const edgeClass = d.edge > 0.005 ? "pos" : d.edge < -0.005 ? "neg" : "zero";

  return (
    <Fragment>
      <tr onClick={() => setOpen((x) => !x)} style={{ cursor: "pointer" }}>
        <td className="rank">{i + 1}</td>
        <td>
          <div className="market-title">{d.title}</div>
          <div className="market-end">ends {d.end_date}</div>
        </td>
        <td>
          <div>
            <span className={`bet-tag ${d.bet_direction === "YES" ? "yes" : "no"}`}>
              {d.bet_direction}
            </span>
          </div>
          <div className="bet-fraction">{pct(d.bet_fraction, 2)} stake</div>
        </td>
        <td>
          <div className="prices">
            <span style={{ color: "#78716C" }}>{pct(d.market_price, 1)}</span>
            <span className="arrow">→</span>
            <span style={{ fontWeight: 500 }}>{pct(d.estimated_prob, 1)}</span>
          </div>
        </td>
        <td>
          <span className={`edge-val ${edgeClass}`}>{signedPct(d.edge)}</span>
        </td>
        <td>
          <div className="conf-bar">
            {Array.from({ length: 10 }, (_, idx) => (
              <div key={idx} className={`conf-pip ${idx < d.confidence ? "on" : ""}`} />
            ))}
          </div>
          <div style={{ fontSize: 10, color: "#A8A29E", marginTop: 3 }}>{d.confidence}/10</div>
        </td>
        <td className="outcome-cell">
          {d.won === null ? (
            <span className="outcome-open">Open</span>
          ) : d.won ? (
            <span className="outcome-won">✓ Won</span>
          ) : (
            <span className="outcome-lost">✗ Lost</span>
          )}
        </td>
        <td className="pnl-cell">
          {d.pnl === null ? (
            <span className="pnl-open">—</span>
          ) : (
            <span className={d.pnl >= 0 ? "pnl-pos" : "pnl-neg"}>
              {signedPct(d.pnl, 2)}
            </span>
          )}
        </td>
      </tr>
      {open && d.rationale && (
        <tr className="rationale-row">
          <td colSpan={8}>{d.rationale}</td>
        </tr>
      )}
    </Fragment>
  );
}

// ── Decisions table ───────────────────────────────────────────────────────

function DecisionsTab({ decisions }: { decisions: Decision[] }) {
  if (decisions.length === 0)
    return <div className="empty">No decisions for this run</div>;

  const resolved = decisions.filter((d) => d.won !== null);
  const won = resolved.filter((d) => d.won).length;
  const totalPnl = resolved.reduce((s, d) => s + (d.pnl ?? 0), 0);

  return (
    <>
      {resolved.length > 0 && (
        <div style={{
          display: "flex", gap: 20, padding: "8px 12px",
          background: "#FDFCFB", borderBottom: "1px solid #E8E3DC",
          fontSize: 11, color: "#78716C", flexShrink: 0,
        }}>
          <span>{resolved.length} resolved</span>
          <span>Win rate: <strong style={{ color: "#1C1917" }}>{((won / resolved.length) * 100).toFixed(0)}%</strong> ({won}/{resolved.length})</span>
          <span>Run P&L: <strong style={{ color: totalPnl >= 0 ? "#15803D" : "#DC2626" }}>{signedPct(totalPnl, 2)}</strong></span>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Market</th>
              <th>Bet</th>
              <th>Mkt → Est</th>
              <th>Edge</th>
              <th>Conf</th>
              <th>Outcome</th>
              <th>P&L</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((d, i) => (
              <DecisionRow key={d.market_id} d={d} i={i} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ── Logs tab ──────────────────────────────────────────────────────────────

function LogsTab({ logs }: { logs: Logs | null }) {
  // Filter out noisy HTTP polling lines
  const lines = (logs?.lines ?? []).filter(
    (l) => !l.includes("getUpdates") && !l.includes("HTTP Request")
  );
  return (
    <div className="logs-wrap">
      <pre className="logs">
        {lines.length ? lines.join("\n") : "No logs yet."}
      </pre>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [logs, setLogs] = useState<Logs | null>(null);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [tab, setTab] = useState<"picks" | "logs">("picks");
  const [loading, setLoading] = useState(true);

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

  useEffect(() => {
    if (!selectedRun) return;
    api.decisions(selectedRun).then(setDecisions).catch(() => setDecisions([]));
  }, [selectedRun]);

  if (loading)
    return <div className="empty" style={{ height: "100vh" }}>Loading…</div>;

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div>
          <span className="brand">PrediBronx</span>
          <span className="brand-sub">Polymarket AI bot</span>
        </div>
        <StatusPill health={health} />
      </header>

      {/* Stats bar */}
      <StatsBar data={performance} />

      {/* Body */}
      <div className="body">
        {/* Sidebar: run history */}
        <Sidebar runs={runs} selected={selectedRun} onSelect={setSelectedRun} />

        {/* Main content */}
        <div className="content">
          <div className="content-header">
            <div>
              <span className="content-title">
                {selectedRun ? `Picks — ${selectedRun}` : "Latest picks"}
              </span>
              {decisions.length > 0 && (
                <span className="content-meta" style={{ marginLeft: 8 }}>
                  {decisions.length} markets · click row for rationale
                </span>
              )}
            </div>
            <div className="tabs">
              <button
                className={`tab-btn ${tab === "picks" ? "active" : ""}`}
                onClick={() => setTab("picks")}
              >
                Picks
              </button>
              <button
                className={`tab-btn ${tab === "logs" ? "active" : ""}`}
                onClick={() => setTab("logs")}
              >
                Bot logs
              </button>
            </div>
          </div>

          {tab === "picks" ? (
            <DecisionsTab decisions={decisions} />
          ) : (
            <LogsTab logs={logs} />
          )}
        </div>
      </div>
    </div>
  );
}
