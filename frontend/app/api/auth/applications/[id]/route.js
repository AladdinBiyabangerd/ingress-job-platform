import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function DELETE(request, context) {
  const { id } = await context.params;
  if (!/^\d+$/.test(String(id))) return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/applications/${id}`, { method: "DELETE" });
  if (upstream.status === 204) {
    return noStore(appendCookies(new Response(null, { status: 204 }), setCookies));
  }
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
