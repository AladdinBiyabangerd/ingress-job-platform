import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

function jobPath(jobId) {
  const id = String(jobId || "").trim();
  if (!/^\d+$/.test(id)) return null;
  return `/api/v1/me/saved-jobs/${id}`;
}

export async function POST(request, { params }) {
  const { jobId } = await params;
  const path = jobPath(jobId);
  if (!path) return noStore(Response.json({ detail: "Not found" }, { status: 404 }));
  const { upstream, setCookies } = await authorizedApi(request, path, { method: "POST" });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}

export async function DELETE(request, { params }) {
  const { jobId } = await params;
  const path = jobPath(jobId);
  if (!path) return noStore(Response.json({ detail: "Not found" }, { status: 404 }));
  const { upstream, setCookies } = await authorizedApi(request, path, { method: "DELETE" });
  if (upstream.status === 204) {
    return noStore(appendCookies(new Response(null, { status: 204 }), setCookies));
  }
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
