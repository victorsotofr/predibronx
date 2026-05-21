import { archivedLogs, fetchBackendJson } from "../lib/archive.js";

const API_URL = process.env.PREDIBRONX_API_URL || "http://localhost:8080";

export default async function handler(req, res) {
  const lines = new URL(req.url, "http://localhost").searchParams.get("lines") || "80";

  try {
    const { status, data } = await fetchBackendJson(`${API_URL}/logs?lines=${lines}`);
    res.status(status).json(data);
  } catch {
    res.status(200).json(archivedLogs(lines));
  }
}
