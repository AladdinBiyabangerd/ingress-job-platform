import { adPayload } from "../../../../../lib/server/ad";
import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

async function relay(upstream, setCookies) {
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}

export async function GET(request) {
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/cabinet/jobs");
  return relay(upstream, setCookies);
}

export async function POST(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/cabinet/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(adPayload(body)),
  });
  return relay(upstream, setCookies);
}
