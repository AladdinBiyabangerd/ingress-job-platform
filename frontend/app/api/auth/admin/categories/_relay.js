import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export async function relay(request, path, method = "GET", withBody = false) {
  const init = { method };
  if (withBody) {
    let body = {};
    try {
      body = await request.json();
    } catch {
      return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
    }
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body && typeof body === "object" ? body : {});
  }
  const { upstream, setCookies } = await authorizedApi(request, path, init);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
