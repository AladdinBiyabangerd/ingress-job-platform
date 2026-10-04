import { appendCookies, authorizedApi, noStore } from "../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function PATCH(request, context) {
  const { id } = await context.params;
  if (!/^\d+$/.test(String(id))) return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const status = typeof body.status === "string" ? body.status : "";
  const reason = typeof body.reason === "string" ? body.reason : "";
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/admin/applications/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, reason }),
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
