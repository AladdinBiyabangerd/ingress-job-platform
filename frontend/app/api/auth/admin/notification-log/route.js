import { appendCookies, authorizedApi, noStore } from "../../../../../lib/server/oidc";
import { notificationLogQuery } from "../../../../../lib/admin-notification-log";

export const runtime = "nodejs";

export async function GET(request) {
  const url = new URL(request.url);
  const query = notificationLogQuery({
    user: url.searchParams.get("user") || "",
    days: url.searchParams.get("days") || 30,
  });
  const { upstream, setCookies } = await authorizedApi(request, `/api/v1/admin/notification-log?${query}`);
  const payload = await upstream.json().catch(() => ({}));
  return noStore(
    appendCookies(Response.json(payload, { status: upstream.status || 502 }), setCookies),
  );
}
