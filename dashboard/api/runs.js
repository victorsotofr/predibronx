import { fetchBackendJson, loadArchive } from "../lib/archive.js";

const API_URL = process.env.PREDIBRONX_API_URL || "http://localhost:8080";

export default async function handler(req, res) {
  try {
    const { status, data } = await fetchBackendJson(`${API_URL}/runs`);
    res.status(status).json(data);
  } catch {
    res.status(200).json(loadArchive().runs);
  }
}
