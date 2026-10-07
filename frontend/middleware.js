import { NextResponse } from "next/server";
import { apiBase } from "./lib/api";
import { appendCookies, ensureSession, publicOrigin } from "./lib/server/oidc";

const COMPANY = new Set(["/company", "/en/company", "/ru/company"]);

/** Employer routes that must redirect when company profile is incomplete. */
function needsCompanyGate(pathname) {
  const path = pathname.replace(/^\/(en|ru)(?=\/|$)/, "") || "/";
  return path === "/post" || path.startsWith("/post/") || path === "/admin" || path.startsWith("/admin/");
}

function localeOf(pathname) {
  if (pathname === "/en" || pathname.startsWith("/en/")) return "en";
  if (pathname === "/ru" || pathname.startsWith("/ru/")) return "ru";
  return "az";
}

function pass(request, locale, setCookies = []) {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-locale", locale);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  return setCookies.length ? appendCookies(response, setCookies) : response;
}

export async function middleware(request) {
  const { pathname } = request.nextUrl;
  const locale = localeOf(pathname);
  if (pathname.startsWith("/api") || pathname.startsWith("/_next") || COMPANY.has(pathname)) {
    return pass(request, locale);
  }
  // Public browse (home/jobs/companies/trends) never waits on /me.
  if (!needsCompanyGate(pathname)) {
    return pass(request, locale);
  }
  if (request.cookies.get("job_guest")?.value) return pass(request, locale);
  const session = await ensureSession(request);
  if (!session.access) return pass(request, locale, session.setCookies);
  try {
    const me = await fetch(`${apiBase()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${session.access}`, Accept: "application/json" },
      cache: "no-store",
    });
    if (!me.ok) return pass(request, locale, session.setCookies);
    const data = await me.json();
    if (data.needs_company_profile) {
      const prefix = locale === "az" ? "" : `/${locale}`;
      const redirect = NextResponse.redirect(new URL(`${prefix}/company`, publicOrigin(request)));
      return session.setCookies.length ? appendCookies(redirect, session.setCookies) : redirect;
    }
  } catch {
    return pass(request, locale, session.setCookies);
  }
  return pass(request, locale, session.setCookies);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
