import { apiBase } from "../../../lib/api";

export const runtime = "nodejs";

/** Public jobs list proxy — browser cannot reach Railway private API host. */
export async function GET(request) {
  const qs = new URL(request.url).searchParams.toString();
  const path = qs ? `/api/v1/jobs?${qs}` : "/api/v1/jobs";
  const upstream = `${apiBase()}${path}`;
  try {
    const res = await fetch(upstream, {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    const payload = await res.json().catch(() => ({}));
    return Response.json(payload, {
      status: res.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    console.error("[api/jobs] upstream failed", {
      base: apiBase(),
      message: err instanceof Error ? err.message : String(err),
    });
    return Response.json(
      { items: [], total: 0, page: 1, per_page: 20, pages: 1, catalog_total: 0, facets: {} },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
