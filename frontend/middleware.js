import { NextResponse } from "next/server";
import { apiBase } from "./lib/api";
import { appendCookies, ensureSession, publicOrigin } from "./lib/server/oidc";

const COMPANY = new Set(["/company", "/en/company", "/ru/company"]);

/** Employer routes that must redirect when company profile is incomplete. */
function needsCompanyGate(pathname) {
  const path = pathname.replace(/^\/(en|ru)(?=\/|$)/, "") || "/";
  return (
    path === "/post"
    || path.startsWith("/post/")
    || path === "/talent"
    || path.startsWith("/talent/")
    || path === "/admin"
    || path.startsWith("/admin/")
  );
}

function localeOf(pathname) {
  if (pathname === "/en" || pathname.startsWith("/en/")) return "en";
  if (pathname === "/ru" || pathname.startsWith("/ru/")) return "ru";
  return "az";
}

function hasSessionCookies(request) {
  return Boolean(request.cookies.get("job_at")?.value || request.cookies.get("job_rt")?.value);
}

/**
 * Pass through with locale (+ optional refreshed session).
 * Forwards access on the request so RSC never calls cookies().set().
 */
function pass(request, locale, session = null) {
  const requestHeaders = new Headers(request.headers);
  // Never trust a client-supplied access header.
  requestHeaders.delete("x-job-access");
  requestHeaders.set("x-locale", locale);
  if (session?.access) {
    requestHeaders.set("x-job-access", session.access);
  }
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  const setCookies = session?.setCookies || [];
  return setCookies.length ? appendCookies(response, setCookies) : response;
}

export async function middleware(request) {
  const { pathname } = request.nextUrl;
  const locale = localeOf(pathname);
  if (pathname.startsWith("/api") || pathname.startsWith("/_next")) {
    return pass(request, locale);
  }

  // Cookie refresh belongs here (Set-Cookie on the response). RSC may only read.
  let session = null;
  if (!request.cookies.get("job_guest")?.value && hasSessionCookies(request)) {
    session = await ensureSession(request);
  }

  // Company profile page and public browse skip the incomplete-profile gate.
  if (COMPANY.has(pathname) || !needsCompanyGate(pathname)) {
    return pass(request, locale, session);
  }

  if (!session?.access) return pass(request, locale, session);
  try {
    const me = await fetch(`${apiBase()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${session.access}`, Accept: "application/json" },
      cache: "no-store",
    });
    if (!me.ok) return pass(request, locale, session);
    const data = await me.json();
    if (data.needs_company_profile) {
      const prefix = locale === "az" ? "" : `/${locale}`;
      const redirect = NextResponse.redirect(new URL(`${prefix}/company`, publicOrigin(request)));
      return session.setCookies.length ? appendCookies(redirect, session.setCookies) : redirect;
    }
  } catch {
    return pass(request, locale, session);
  }
  return pass(request, locale, session);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
