import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {
  const url = new URL(request.url);
  const raw = Number(url.searchParams.get("days") || 7);
  const days = Number.isFinite(raw) ? Math.max(1, Math.min(90, Math.trunc(raw))) : 7;
  const { upstream, setCookies } = await authorizedApi(
    request,
    `/api/v1/admin/ops-status?days=${days}`,
  );
  const payload = await upstream.json().catch(() => ({}));
  return noStore(
    appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies),
  );
}
