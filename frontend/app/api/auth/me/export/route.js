import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/me/export", {
    headers: { Accept: "application/zip" },
  });
  if (!upstream.ok) {
    const payload = await upstream.json().catch(() => ({}));
    return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
  }
  const body = await upstream.arrayBuffer();
  const headers = new Headers();
  headers.set("Content-Type", upstream.headers.get("Content-Type") || "application/zip");
  headers.set(
    "Content-Disposition",
    upstream.headers.get("Content-Disposition") || 'attachment; filename="ingress-job-export.zip"',
  );
  headers.set("Cache-Control", "no-store");
  return appendCookies(new Response(body, { status: 200, headers }), setCookies);
}
