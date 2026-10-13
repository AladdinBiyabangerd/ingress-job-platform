import { apiBase } from "../../../../lib/api";
import { withRateLimit } from "../../../../lib/server/rate-limit";

export const runtime = "nodejs";

/** Public related-skills proxy — browser cannot reach private API host. */
export async function GET(request) {
  return withRateLimit(request, "public_read", async () => {
    const qs = new URL(request.url).searchParams.toString();
    const path = qs ? `/api/v1/skills/related?${qs}` : "/api/v1/skills/related";
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
      console.error("[api/skills/related] upstream failed", {
        base: apiBase(),
        message: err instanceof Error ? err.message : String(err),
      });
      return Response.json(
        { name: "", skill_id: null, items: [] },
        { status: 502, headers: { "Cache-Control": "no-store" } },
      );
    }
  });
}
