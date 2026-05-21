import fs from "node:fs";
import path from "node:path";

const ARCHIVE_PATH = path.join(process.cwd(), "public", "archive.json");
const API_TIMEOUT_MS = Number(process.env.PREDIBRONX_API_TIMEOUT_MS || 1500);

let archiveCache = null;

export function loadArchive() {
  if (!archiveCache) {
    archiveCache = JSON.parse(fs.readFileSync(ARCHIVE_PATH, "utf8"));
  }
  return archiveCache;
}

export async function fetchBackendJson(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`Backend returned ${response.status}`);
    return {
      status: response.status,
      data: await response.json(),
    };
  } finally {
    clearTimeout(timeout);
  }
}

export function archivedDecisions(runDate) {
  const archive = loadArchive();
  const selectedRun = runDate || archive.runs[0]?.run_date;
  return selectedRun ? archive.decisions[selectedRun] || [] : [];
}

export function archivedLogs(lines) {
  const archive = loadArchive();
  const n = Math.min(Math.max(Number(lines) || 80, 0), 500);
  return { lines: archive.logs.lines.slice(-n) };
}
