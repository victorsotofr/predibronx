import type { Decision } from "@/app/page";

function EdgeBadge({ edge }: { edge: number }) {
  const pct = (edge * 100).toFixed(1);
  const positive = edge >= 0;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold ${
        positive
          ? "bg-green-900/40 text-green-400"
          : "bg-red-900/40 text-red-400"
      }`}
    >
      {positive ? "+" : ""}
      {pct}%
    </span>
  );
}

function ConfidenceDots({ value }: { value: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 10 }, (_, i) => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${
            i < value ? "bg-[#7c6af7]" : "bg-[#2a2d3e]"
          }`}
        />
      ))}
    </div>
  );
}

function OutcomeBadge({ resolved_yes }: { resolved_yes: number | null }) {
  if (resolved_yes === null) return <span className="text-xs text-gray-500">Open</span>;
  return resolved_yes ? (
    <span className="text-xs text-green-400">YES</span>
  ) : (
    <span className="text-xs text-red-400">NO</span>
  );
}

export default function DecisionsPanel({
  decisions,
  selectedRun,
}: {
  decisions: Decision[];
  selectedRun: string | null;
}) {
  return (
    <div className="rounded-xl border border-[#2a2d3e] bg-[#1a1d2e] overflow-hidden">
      <div className="px-4 py-3 border-b border-[#2a2d3e]">
        <h2 className="text-sm font-semibold text-white">
          {selectedRun ? `Picks — ${selectedRun}` : "Latest picks"}
        </h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {decisions.length} markets · sorted by edge
        </p>
      </div>

      {decisions.length === 0 ? (
        <div className="px-4 py-10 text-center text-sm text-gray-500">
          No decisions found
        </div>
      ) : (
        <div className="divide-y divide-[#2a2d3e]">
          {decisions.map((d, i) => (
            <div key={d.market_id} className="px-4 py-3 hover:bg-white/[0.02] transition-colors">
              <div className="flex items-start gap-3">
                {/* Rank */}
                <span className="text-xs text-gray-600 w-5 shrink-0 mt-0.5">
                  {i + 1}
                </span>

                <div className="flex-1 min-w-0">
                  {/* Title + market link */}
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-white leading-snug">
                      {d.title}
                    </p>
                    <OutcomeBadge resolved_yes={d.resolved_yes} />
                  </div>

                  {/* Meta row */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5">
                    {/* Direction + prices */}
                    <span
                      className={`text-xs font-semibold ${
                        d.bet_direction === "YES" ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {d.bet_direction}
                    </span>
                    <span className="text-xs text-gray-500 font-mono">
                      Mkt {(d.market_price * 100).toFixed(0)}% → Est{" "}
                      {(d.estimated_prob * 100).toFixed(0)}%
                    </span>
                    <EdgeBadge edge={d.edge} />
                    <span className="text-xs text-gray-500">
                      Ends {d.end_date}
                    </span>
                  </div>

                  {/* Confidence */}
                  <div className="flex items-center gap-2 mt-1.5">
                    <ConfidenceDots value={d.confidence} />
                    <span className="text-xs text-gray-600">{d.confidence}/10</span>
                  </div>

                  {/* Rationale */}
                  {d.rationale && (
                    <p className="text-xs text-gray-400 mt-1.5 leading-relaxed">
                      {d.rationale}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
