import { NextResponse } from "next/server";
import { clearAuthCookiesOn, noStore, oidcConfig, safeReturnTo } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export async function POST(request) {
  const url = new URL(request.url);
  const config = oidcConfig(request);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo") || "/");
  // Stay on the job site. Do not send the browser to Academy logout or authorize.
  const location = new URL(returnTo, config.origin).toString();
  // 200 + client navigation applies Set-Cookie more reliably than a bare 303 in
  // some browsers/proxies; old Tofig tokens were surviving the redirect logout.
  const html = `<!doctype html><html lang="az"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=${escapeHtml(location)}"><title>Çıxış</title></head><body><p>Çıxış edildi.</p><script>location.replace(${JSON.stringify(location)})</script></body></html>`;
  const response = new NextResponse(html, {
    status: 200,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
  return noStore(clearAuthCookiesOn(response, request));
}
