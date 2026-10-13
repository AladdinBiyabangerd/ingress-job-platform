import { appendCookies, authorizedApi, noStore } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {
  const incoming = new URL(request.url).searchParams;
  const qs = new URLSearchParams();
  const limit = Number(incoming.get("limit"));
  const before = Number(incoming.get("before"));
  if (Number.isInteger(limit) && limit > 0) qs.set("limit", String(Math.min(limit, 50)));
  if (Number.isInteger(before) && before > 0) qs.set("before", String(before));
  const path = qs.toString() ? `/api/v1/notifications?${qs}` : "/api/v1/notifications";
  const { upstream, setCookies } = await authorizedApi(request, path);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
