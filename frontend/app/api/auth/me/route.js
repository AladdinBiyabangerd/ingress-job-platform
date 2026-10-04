import { appendCookies, authorizedApi, noStore } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/me");
  if (!upstream.ok) {
    return noStore(appendCookies(Response.json({ authenticated: false }), setCookies));
  }
  const data = await upstream.json();
  return noStore(appendCookies(Response.json(data), setCookies));
}
