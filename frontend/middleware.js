import { NextResponse } from "next/server";
import { apiBase } from "./lib/api";
import { publicOrigin } from "./lib/server/oidc";

const COMPANY = new Set(["/company", "/en/company", "/ru/company"]);

function localeOf(pathname) {
  if (pathname === "/en" || pathname.startsWith("/en/")) return "en";
  if (pathname === "/ru" || pathname.startsWith("/ru/")) return "ru";
  return "az";
}

function pass(request, locale) {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-locale", locale);
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export async function middleware(request) {
  const { pathname } = request.nextUrl;
  const locale = localeOf(pathname);
  if (pathname.startsWith("/api") || pathname.startsWith("/_next") || COMPANY.has(pathname)) {
    return pass(request, locale);
  }
  if (request.cookies.get("job_guest")?.value) return pass(request, locale);
  const access = request.cookies.get("job_access_token")?.value;
  if (!access) return pass(request, locale);
  try {
    const me = await fetch(`${apiBase()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${access}`, Accept: "application/json" },
      cache: "no-store",
    });
    if (!me.ok) return pass(request, locale);
    const data = await me.json();
    if (data.needs_company_profile) {
      const prefix = locale === "az" ? "" : `/${locale}`;
      return NextResponse.redirect(new URL(`${prefix}/company`, publicOrigin(request)));
    }
  } catch {
    return pass(request, locale);
  }
  return pass(request, locale);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
