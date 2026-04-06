import { Suspense } from "react";
import RunsPanel from "@/components/RunsPanel";
import DecisionsPanel from "@/components/DecisionsPanel";
import PerformancePanel from "@/components/PerformancePanel";
import LogsPanel from "@/components/LogsPanel";
import StatusBar from "@/components/StatusBar";

export const revalidate = 60; // refresh every minute

async function fetchApi<T>(path: string, params?: string): Promise<T> {
  const apiUrl = process.env.PREDIBRONX_API_URL ?? "http://localhost:8080";
  const url = `${apiUrl}/${path}${params ? `?${params}` : ""}`;
  const res = await fetch(url, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export type HealthData = {
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

export type PerformanceData = {
  total_runs: number;
  total_resolved: number;
  avg_brier: number | null;
  avg_market_brier: number | null;
  random_baseline: number;
  cumulative_return: number;
  verdict: "beating_market" | "better_than_random" | "worse_than_random" | null;
};

export type LogsData = { lines: string[] };

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ run?: string }>;
}) {
  const { run } = await searchParams;

  const [health, runs, decisions, performance, logs] = await Promise.all([
    fetchApi<HealthData>("health").catch(() => null),
    fetchApi<RunSummary[]>("runs").catch(() => []),
    fetchApi<Decision[]>("decisions", run ? `run_date=${run}` : undefined).catch(() => []),
    fetchApi<PerformanceData>("performance").catch(() => null),
    fetchApi<LogsData>("logs", "lines=80").catch(() => ({ lines: [] })),
  ]);

  const selectedRun = run ?? decisions[0]?.run_date ?? null;

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            PrediBronx
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">
            AI-powered Polymarket prediction bot
          </p>
        </div>
        <Suspense>
          <StatusBar health={health} />
        </Suspense>
      </div>

      {/* Performance strip */}
      <PerformancePanel data={performance} />

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Runs sidebar */}
        <div className="lg:col-span-1">
          <RunsPanel runs={runs} selectedRun={selectedRun} />
        </div>

        {/* Decisions table */}
        <div className="lg:col-span-2">
          <DecisionsPanel decisions={decisions} selectedRun={selectedRun} />
        </div>
      </div>

      {/* Logs */}
      <LogsPanel logs={logs} />
    </main>
  );
}
