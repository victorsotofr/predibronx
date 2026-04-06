import type { HealthData } from "@/app/page";

export default function StatusBar({ health }: { health: HealthData | null }) {
  if (!health) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-900/30 border border-red-800/50">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        <span className="text-xs text-red-400">API unreachable</span>
      </div>
    );
  }

  const daysSinceRun = health.last_run
    ? Math.floor(
        (Date.now() - new Date(health.last_run).getTime()) / 86_400_000
      )
    : null;
  const isStale = daysSinceRun !== null && daysSinceRun > 1;

  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs ${
          isStale
            ? "bg-yellow-900/30 border-yellow-800/50 text-yellow-400"
            : "bg-green-900/30 border-green-800/50 text-green-400"
        }`}
      >
        <span
          className={`w-2 h-2 rounded-full ${isStale ? "bg-yellow-500" : "bg-green-500 animate-pulse"}`}
        />
        {isStale
          ? `Stale — last run ${daysSinceRun}d ago`
          : `Live — last run ${health.last_run}`}
      </div>
    </div>
  );
}
