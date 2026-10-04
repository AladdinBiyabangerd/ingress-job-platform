import { appendCookies, authorizedApi, noStore } from "../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request, context) {
  const { id } = await context.params;
  if (!/^\d+$/.test(String(id))) return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/jobs/${id}/original`);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
