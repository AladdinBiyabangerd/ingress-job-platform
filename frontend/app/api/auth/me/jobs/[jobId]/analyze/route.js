import { appendCookies, authorizedApi, noStore } from "../../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request, context) {
  const { jobId } = await context.params;
  if (!/^\d+$/.test(String(jobId))) {
    return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  }
  const url = new URL(request.url);
  const qs = url.searchParams.toString();
  const path = qs
    ? `/api/v1/me/jobs/${jobId}/analyze?${qs}`
    : `/api/v1/me/jobs/${jobId}/analyze`;
  const { upstream, setCookies } = await authorizedApi(request, path);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(
    appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies),
  );
}
