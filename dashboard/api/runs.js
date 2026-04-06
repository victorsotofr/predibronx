const API_URL = process.env.PREDIBRONX_API_URL || "http://localhost:8080";

export default async function handler(req, res) {
  try {
    const r = await fetch(`${API_URL}/runs`);
    res.status(r.status).json(await r.json());
  } catch {
    res.status(502).json({ error: "unreachable" });
  }
}
