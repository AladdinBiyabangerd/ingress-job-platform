import { appendCookies, authorizedApi, noStore } from "../../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request, context) {
  const { id } = await context.params;
  if (!/^\d+$/.test(String(id))) return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  let reason = "";
  try {
    const body = await request.json();
    if (body && typeof body.reason === "string") reason = body.reason;
  } catch {
    reason = "";
  }
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/admin/jobs/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
