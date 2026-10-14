import { apiBase } from "../../../lib/api";
import { appendCookies, authorizedApi, noStore } from "../../../lib/server/oidc";
import { withRateLimit } from "../../../lib/server/rate-limit";

export const runtime = "nodejs";

/** Public jobs list proxy — browser cannot reach Railway private API host.
 * When `viewed=true`, forward the session so the API can scope to that user.
 */
export async function GET(request) {
  return withRateLimit(request, "public_read", async () => {
    const search = new URL(request.url).searchParams;
    const qs = search.toString();
    const path = qs ? `/api/v1/jobs?${qs}` : "/api/v1/jobs";
    const wantsViewed =
      search.get("viewed") === "true" ||
      search.get("viewed") === "1" ||
      search.get("viewed") === "yes";

    if (wantsViewed) {
      try {
        const { upstream, setCookies } = await authorizedApi(request, path);
        const payload = await upstream.json().catch(() => ({}));
        // Guests: authorizedApi returns 401 — fall through to unauthenticated
        // call so the API returns an empty viewed board instead of a hard error.
        if (upstream.status && upstream.status !== 401) {
          return noStore(
            appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies),
          );
        }
      } catch (err) {
        console.error("[api/jobs] viewed auth proxy failed", {
          message: err instanceof Error ? err.message : String(err),
        });
      }
    }

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
  });
}
