import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

async function relay(upstream, setCookies) {
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}

export async function GET(request) {
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/admin/ai-flags");
  return relay(upstream, setCookies);
}

export async function PUT(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const flags = body && typeof body.flags === "object" && body.flags !== null ? body.flags : {};
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/admin/ai-flags", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ flags }),
  });
  return relay(upstream, setCookies);
}
