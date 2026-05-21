import { archivedDecisions, fetchBackendJson } from "../lib/archive.js";

const API_URL = process.env.PREDIBRONX_API_URL || "http://localhost:8080";

export default async function handler(req, res) {
  const run_date = new URL(req.url, "http://localhost").searchParams.get("run_date");

  try {
    const url = run_date
      ? `${API_URL}/decisions?run_date=${run_date}`
      : `${API_URL}/decisions`;
    const { status, data } = await fetchBackendJson(url);
    res.status(status).json(data);
  } catch {
    res.status(200).json(archivedDecisions(run_date));
  }
}
