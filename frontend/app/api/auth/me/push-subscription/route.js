import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/me/push-subscription", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: body.endpoint,
      keys: body.keys || {},
    }),
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}

export async function DELETE(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/me/push-subscription", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: body.endpoint }),
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
