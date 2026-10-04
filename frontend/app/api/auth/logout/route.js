import { appendCookies, clearAuthCookies, noStore, oidcConfig, safeReturnTo } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  const url = new URL(request.url);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo") || "/");
  const response = new Response(null, {
    status: 303,
    headers: { Location: new URL(returnTo, oidcConfig(request).origin).toString() },
  });
  return noStore(appendCookies(response, clearAuthCookies()));
}
