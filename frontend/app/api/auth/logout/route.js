import { appendCookies, clearAuthCookies, noStore, safeReturnTo } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  const url = new URL(request.url);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo") || "/");
  const response = new Response(null, {
    status: 303,
    headers: { Location: new URL(returnTo, url.origin).toString() },
  });
  return noStore(appendCookies(response, clearAuthCookies()));
}
