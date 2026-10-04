import { appendCookies, authorizedApi, noStore } from "../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request, context) {
  const { id } = await context.params;
  if (!/^\d+$/.test(String(id))) return noStore(new Response("not found", { status: 404 }));
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/applications/${id}/cv`);
  const headers = new Headers();
  const type = upstream.headers.get("content-type");
  if (type) headers.set("content-type", type);
  const disposition = upstream.headers.get("content-disposition");
  if (disposition) headers.set("content-disposition", disposition);
  headers.set("cache-control", "no-store, max-age=0");
  const bytes = await upstream.arrayBuffer();
  return appendCookies(new Response(bytes, { status: upstream.status || 502, headers }), setCookies);
}
