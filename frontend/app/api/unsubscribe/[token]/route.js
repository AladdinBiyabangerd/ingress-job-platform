import { apiBase } from "../../../../lib/api";
import { noStore } from "../../../../lib/server/oidc";
import { withRateLimit } from "../../../../lib/server/rate-limit";

export const runtime = "nodejs";

export async function GET(request, { params }) {
  return withRateLimit(request, "click_unsub", async () => {
    const resolved = (await params) || {};
    const token = String(resolved.token || "");
    const res = await fetch(`${apiBase()}/api/v1/unsubscribe/${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
    const payload = await res.json().catch(() => ({}));
    return noStore(Response.json(payload, { status: res.status || 502 }));
  });
}

export async function POST(request, { params }) {
  return withRateLimit(request, "click_unsub", async () => {
    const resolved = (await params) || {};
    const token = String(resolved.token || "");
    const res = await fetch(`${apiBase()}/api/v1/unsubscribe/${encodeURIComponent(token)}`, {
      method: "POST",
      cache: "no-store",
    });
    const payload = await res.json().catch(() => ({}));
    return noStore(Response.json(payload, { status: res.status || 502 }));
  });
}
