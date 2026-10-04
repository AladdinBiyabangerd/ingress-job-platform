import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {

  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/admin/applications");
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
