const BASE = "/api";

async function get<T>(path: string, params?: string): Promise<T> {
  const url = `${BASE}/${path}${params ? `?${params}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export type Health = {
  status: string;
  last_run: string | null;
  last_run_decisions: number;
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
