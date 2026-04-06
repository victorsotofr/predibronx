const API_URL = process.env.PREDIBRONX_API_URL || "http://localhost:8080";

export default async function handler(req, res) {
  try {
    const lines = new URL(req.url, "http://localhost").searchParams.get("lines") || "80";
    const r = await fetch(`${API_URL}/logs?lines=${lines}`);
    res.status(r.status).json(await r.json());
  } catch {
    res.status(502).json({ error: "unreachable" });
  }
}
