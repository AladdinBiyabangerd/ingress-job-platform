import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {
  const url = new URL(request.url);
  const qs = url.searchParams.toString();
  const path = qs ? `/api/v1/me/insights?${qs}` : "/api/v1/me/insights";
  const { upstream, setCookies } = await authorizedApi(request, path);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
