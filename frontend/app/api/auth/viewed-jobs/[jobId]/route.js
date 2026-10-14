import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

function upstreamPath(jobId) {
  const id = Number(jobId);
  if (!Number.isInteger(id) || id <= 0) return null;
  return `/api/v1/me/viewed-jobs/${id}`;
}

export async function POST(request, { params }) {
  const { jobId } = await params;
  const path = upstreamPath(jobId);
  if (!path) {
    return noStore(Response.json({ detail: "Elan tapılmadı" }, { status: 404 }));
  }
  const { upstream, setCookies } = await authorizedApi(request, path, { method: "POST" });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
