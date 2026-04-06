const API_URL = process.env.PREDIBRONX_API_URL || "http://localhost:8080";

export default async function handler(req, res) {
  const segments = Array.isArray(req.query.path)
    ? req.query.path.join("/")
    : req.query.path || "";

  const url = new URL(req.url, "http://localhost");
  const upstream = `${API_URL}/${segments}${url.search}`;

  try {
    const r = await fetch(upstream);
    const data = await r.json();
    res.status(r.status).json(data);
  } catch {
    res.status(502).json({ error: "Could not reach API" });
  }
}
