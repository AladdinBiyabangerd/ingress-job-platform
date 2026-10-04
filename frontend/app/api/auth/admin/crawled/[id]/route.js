import { appendCookies, authorizedApi, noStore } from "../../../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function PATCH(request, context) {

  const { id } = await context.params;
  if (!/^\d+$/.test(String(id))) return noStore(Response.json({ detail: "not_found" }, { status: 404 }));

  let body = {};
  try {
    body = await request.json();
  } catch {
    return noStore(Response.json({ detail: "invalid" }, { status: 400 }));
  }
  const payload = {
    title: body.title || "",
    company: body.company || "",
    city: body.city || "",
    remote: Boolean(body.remote),
    text: body.text || "",
    language: body.language || "",
    salary: body.salary || "",
    job_type: body.job_type || "",
  };

  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/admin/crawled/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const saved = await upstream.json().catch(() => ({}));
  return noStore(appendCookies(Response.json(saved, { status: upstream.status || 502 }), setCookies));
}
