import Link from "next/link";
import type { RunSummary } from "@/app/page";

export default function RunsPanel({
  runs,
  selectedRun,
}: {
  runs: RunSummary[];
  selectedRun: string | null;
}) {
  return (
    <div className="rounded-xl border border-[#2a2d3e] bg-[#1a1d2e] overflow-hidden">
      <div className="px-4 py-3 border-b border-[#2a2d3e]">
        <h2 className="text-sm font-semibold text-white">Run history</h2>
        <p className="text-xs text-gray-500 mt-0.5">{runs.length} days logged</p>
      </div>
      <ul className="divide-y divide-[#2a2d3e] max-h-[500px] overflow-y-auto">
        {runs.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-gray-500">No runs yet</li>
        )}
        {runs.map((r) => {
          const isSelected = r.run_date === selectedRun;
          return (
            <li key={r.run_date}>
              <Link
                href={`/?run=${r.run_date}`}
                className={`flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors ${
                  isSelected ? "bg-[#7c6af7]/10 border-l-2 border-[#7c6af7]" : ""
                }`}
              >
                <div>
                  <p className="text-sm font-medium text-white">{r.run_date}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {r.n_decisions} markets · avg conf{" "}
                    {r.avg_confidence.toFixed(1)}/10
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-mono text-[#7c6af7]">
                    max {(r.max_edge * 100).toFixed(1)}%
                  </p>
                  <p className="text-xs text-gray-500">edge</p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
