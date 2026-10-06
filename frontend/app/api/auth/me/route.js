import { appendCookies, authorizedApi, noStore } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {
  const lang = new URL(request.url).searchParams.get("lang") || "";
  const path = lang ? `/api/v1/me?lang=${encodeURIComponent(lang)}` : "/api/v1/me";
  const { upstream, setCookies } = await authorizedApi(request, path);
  if (!upstream.ok) {
    return noStore(appendCookies(Response.json({ authenticated: false }), setCookies));
  }
  const data = await upstream.json();
  return noStore(appendCookies(Response.json(data), setCookies));
}

export async function DELETE(request) {
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/me", {
    method: "DELETE",
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
