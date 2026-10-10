import { appendCookies, authorizedApi, noStore } from "../../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request, context) {
  const { jobId } = await context.params;
  if (!/^\d+$/.test(String(jobId))) {
    return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  }
  const url = new URL(request.url);
  const qs = url.searchParams.toString();
  const path = qs
    ? `/api/v1/me/jobs/${jobId}/tailored-cv?${qs}`
    : `/api/v1/me/jobs/${jobId}/tailored-cv`;
  let body = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  const { upstream, setCookies } = await authorizedApi(request, path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body && typeof body === "object" ? body : {}),
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(
    appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies),
  );
}
