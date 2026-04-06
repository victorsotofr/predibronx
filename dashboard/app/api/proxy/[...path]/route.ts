import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.PREDIBRONX_API_URL ?? "http://localhost:8080";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const endpoint = path.join("/");
  const search = request.nextUrl.search;

  try {
    const res = await fetch(`${API_URL}/${endpoint}${search}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Upstream error" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Could not reach API" }, { status: 502 });
  }
}
