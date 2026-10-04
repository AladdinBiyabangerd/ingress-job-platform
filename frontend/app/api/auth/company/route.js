import { appendCookies, authorizedApi, noStore } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const { upstream, setCookies } = await authorizedApi(request, "/api/v1/company-profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: body.company_name || "",
      city: body.city || "",
      about: body.about || "",
    }),
  });
  const payload = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies));
}
