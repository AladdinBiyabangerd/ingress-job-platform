import { apiBase } from "../../../lib/api";

export const runtime = "nodejs";

/** Public trends proxy — browser cannot reach private API host. */
export async function GET(request) {
  const qs = new URL(request.url).searchParams.toString();
  const path = qs ? `/api/v1/trends?${qs}` : "/api/v1/trends";
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
    console.error("[api/trends] upstream failed", {
      base: apiBase(),
      message: err instanceof Error ? err.message : String(err),
    });
    return Response.json(
      { items: [], as_of: null, window_days: 7 },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
