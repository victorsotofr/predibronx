import type { PerformanceData } from "@/app/page";

const verdictConfig = {
  beating_market: { label: "Beating the market", color: "text-green-400", bg: "bg-green-900/20 border-green-800/40" },
  better_than_random: { label: "Better than random", color: "text-yellow-400", bg: "bg-yellow-900/20 border-yellow-800/40" },
  worse_than_random: { label: "Worse than random", color: "text-red-400", bg: "bg-red-900/20 border-red-800/40" },
};

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
      <span className="text-xl font-semibold text-white mt-0.5">{value}</span>
      {sub && <span className="text-xs text-gray-500 mt-0.5">{sub}</span>}
    </div>
  );
}

export default function PerformancePanel({ data }: { data: PerformanceData | null }) {
  if (!data) return null;

  const verdict = data.verdict ? verdictConfig[data.verdict] : null;
  const returnColor = data.cumulative_return >= 0 ? "text-green-400" : "text-red-400";

  return (
    <div
      className={`rounded-xl border p-5 ${
        verdict?.bg ?? "bg-[#1a1d2e] border-[#2a2d3e]"
      }`}
    >
      <div className="flex flex-wrap gap-8 items-center">
        <Stat
          label="Total runs"
          value={String(data.total_runs)}
          sub={`${data.total_resolved} resolved`}
        />

        {data.avg_brier !== null ? (
          <>
            <Stat
              label="Avg Brier score"
              value={data.avg_brier.toFixed(4)}
              sub={`Market: ${data.avg_market_brier?.toFixed(4)} · Random: ${data.random_baseline}`}
            />
            <Stat
              label="Cumulative return"
              value={`${data.cumulative_return >= 0 ? "+" : ""}${(data.cumulative_return * 100).toFixed(2)}%`}
            />
            {verdict && (
              <div className={`ml-auto text-sm font-medium ${verdict.color}`}>
                {verdict.label}
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-gray-500">No resolved markets yet — performance will appear once markets close.</p>
        )}
      </div>
    </div>
  );
}
