import { apiBase } from "../../../../lib/api";
import { noStore } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function GET(_request, { params }) {
  const token = params?.token || "";
  const res = await fetch(`${apiBase()}/api/v1/unsubscribe/${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));
  return noStore(Response.json(payload, { status: res.status || 502 }));
}

export async function POST(_request, { params }) {
  const token = params?.token || "";
  const res = await fetch(`${apiBase()}/api/v1/unsubscribe/${encodeURIComponent(token)}`, {
    method: "POST",
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));
  return noStore(Response.json(payload, { status: res.status || 502 }));
}
