import { apiBase } from "../../../lib/api";
import { noStore } from "../../../lib/server/oidc";

export const runtime = "nodejs";

/** Proxy email click tracking → API 302 to the job page. */
export async function GET(_request, { params }) {
  const token = params?.token || "";
  const res = await fetch(`${apiBase()}/api/v1/r/${encodeURIComponent(token)}`, {
    cache: "no-store",
    redirect: "manual",
  });
  const location = res.headers.get("location");
  if (res.status >= 300 && res.status < 400 && location) {
    return noStore(Response.redirect(location, 302));
  }
  const payload = await res.json().catch(() => ({ detail: "invalid_token" }));
  return noStore(Response.json(payload, { status: res.status || 404 }));
}
