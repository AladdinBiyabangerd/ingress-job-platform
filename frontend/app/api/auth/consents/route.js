import { appendCookies, authorizedApi, noStore } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(request) {
  const lang = new URL(request.url).searchParams.get("lang") || "";
  const qs = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/consents${qs}`);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}

export async function PUT(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const lang = new URL(request.url).searchParams.get("lang") || body.lang || "";
  const qs = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/consents${qs}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      matching: body.matching,
      emails: body.emails,
      recruiter_visibility: body.recruiter_visibility,
      visibility: body.visibility,
    }),
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
