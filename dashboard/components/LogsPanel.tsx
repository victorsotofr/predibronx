"use client";

import { useState } from "react";
import type { LogsData } from "@/app/page";

export default function LogsPanel({ logs }: { logs: LogsData }) {
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1.5"
      >
        <span>▶</span>
        Show bot logs ({logs.lines.length} lines)
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-[#2a2d3e] bg-[#0d1117] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#2a2d3e]">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Bot logs
        </h2>
        <button
          onClick={() => setOpen(false)}
          className="text-xs text-gray-600 hover:text-gray-400"
        >
          Hide
        </button>
      </div>
      <div className="p-4 max-h-80 overflow-y-auto">
        <pre className="text-xs text-gray-400 font-mono leading-relaxed whitespace-pre-wrap">
          {logs.lines.length === 0
            ? "No logs yet."
            : logs.lines.join("\n")}
        </pre>
      </div>
    </div>
  );
}
