const BASE = "/api";

type Archive = {
  health: Health;
  runs: RunSummary[];
  decisions: Record<string, Decision[]>;
  performance: Performance;
  logs: Logs;
};

let archivePromise: Promise<Archive> | null = null;

async function archive() {
  archivePromise ??= fetch("/archive.json").then((res) => {
    if (!res.ok) throw new Error(`Archive returned ${res.status}`);
    return res.json();
  });
  return archivePromise;
}

async function fromArchive<T>(path: string, params?: string): Promise<T> {
  const data = await archive();

  if (path === "health") return data.health as T;
  if (path === "runs") return data.runs as T;
  if (path === "performance") return data.performance as T;
  if (path === "logs") {
    const lines = Math.min(
      Math.max(Number(new URLSearchParams(params).get("lines")) || 80, 0),
      500,
    );
    return { lines: data.logs.lines.slice(-lines) } as T;
  }
  if (path === "decisions") {
    const requested = new URLSearchParams(params).get("run_date");
    const runDate = requested || data.runs[0]?.run_date;
    return (runDate ? data.decisions[runDate] ?? [] : []) as T;
  }

  throw new Error(`No archive fallback for ${path}`);
}

async function get<T>(path: string, params?: string): Promise<T> {
  const url = `${BASE}/${path}${params ? `?${params}` : ""}`;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
  } catch {
    return fromArchive<T>(path, params);
  }
}

export type Health = {
  status: string;
  source?: "live" | "archive";
  last_run: string | null;
  last_run_decisions: number;
  experiment_stopped?: boolean;
};

export type RunSummary = {
  run_date: string;
  n_decisions: number;
  avg_edge: number;
  avg_confidence: number;
  max_edge: number;
};

export type Decision = {
  market_id: string;
  title: string;
  end_date: string;
  category: string;
  volume: number;
  run_date: string;
  estimated_prob: number;
  market_price: number;
  bet_direction: "YES" | "NO";
  bet_fraction: number;
  confidence: number;
  rationale: string;
  edge: number;
  resolved_yes: number | null;
  resolved_at: string | null;
  won: boolean | null;
  pnl: number | null;
};

export type Performance = {
  total_runs: number;
  total_resolved: number;
  avg_brier: number | null;
  avg_market_brier: number | null;
  random_baseline: number;
  cumulative_return: number;
  verdict: "beating_market" | "better_than_random" | "worse_than_random" | null;
};

export type Logs = { lines: string[] };

export const api = {
  health: () => get<Health>("health"),
  runs: () => get<RunSummary[]>("runs"),
  decisions: (run_date?: string) =>
    get<Decision[]>("decisions", run_date ? `run_date=${run_date}` : undefined),
  performance: () => get<Performance>("performance"),
  logs: () => get<Logs>("logs", "lines=80"),
};
