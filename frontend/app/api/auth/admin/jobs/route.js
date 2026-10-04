import { adPayload } from "../../../../../lib/server/ad";
import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

async function relay(upstream, setCookies) {
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}

export async function GET(request) {
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/admin/jobs");
  return relay(upstream, setCookies);
}

export async function POST(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const payload = {
    ...adPayload(body),
    source_url: typeof body.source_url === "string" ? body.source_url : "",
  };
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/admin/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return relay(upstream, setCookies);
}
