const API_URL = process.env.PREDIBRONX_API_URL || "http://localhost:8080";

export default async function handler(req, res) {
  try {
    const run_date = new URL(req.url, "http://localhost").searchParams.get("run_date");
    const url = run_date
      ? `${API_URL}/decisions?run_date=${run_date}`
      : `${API_URL}/decisions`;
    const r = await fetch(url);
    res.status(r.status).json(await r.json());
  } catch {
    res.status(502).json({ error: "unreachable" });
  }
}
