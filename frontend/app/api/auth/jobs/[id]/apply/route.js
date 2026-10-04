import { appendCookies, authorizedApi, noStore } from "../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request, context) {
  const { id } = await context.params;
  if (!/^\d+$/.test(String(id))) return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  const type = request.headers.get("content-type") || "";
  const init = { method: "POST" };
  if (type) {
    init.headers = { "content-type": type };
    init.body = Buffer.from(await request.arrayBuffer());
  }
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/jobs/${id}/apply`, init);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
