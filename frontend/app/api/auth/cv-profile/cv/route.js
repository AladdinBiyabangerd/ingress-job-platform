import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  const type = request.headers.get("content-type") || "";
  const init = { method: "POST" };
  if (type) {
    init.headers = { "content-type": type };
    init.body = Buffer.from(await request.arrayBuffer());
  }
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/profile/cv", init);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
