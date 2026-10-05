import { appendCookies, authorizedApi, noStore } from "../../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request, context) {
  const { jobId } = await context.params;
  if (!/^\d+$/.test(String(jobId))) {
    return noStore(Response.json({ detail: "not_found" }, { status: 404 }));
  }
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const { upstream, setCookies } = await authorizedApi(
    request,
    `/api/v1/me/matches/${jobId}/feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vote: body.vote,
        reason: body.reason || "",
      }),
    },
  );
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
