import { NextResponse } from "next/server";
import { apiBase } from "./lib/api";

const COMPANY = new Set(["/company", "/en/company", "/ru/company"]);

export async function middleware(request) {
  const { pathname } = request.nextUrl;
  if (pathname.startsWith("/api") || pathname.startsWith("/_next") || COMPANY.has(pathname)) {
    return NextResponse.next();
  }
  const access = request.cookies.get("job_access_token")?.value;
  if (!access) return NextResponse.next();
  try {
    const me = await fetch(`${apiBase()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${access}`, Accept: "application/json" },
      cache: "no-store",
    });
    if (!me.ok) return NextResponse.next();
    const data = await me.json();
    if (data.needs_company_profile) {
      const prefix = pathname.startsWith("/en") ? "/en" : pathname.startsWith("/ru") ? "/ru" : "";
      return NextResponse.redirect(new URL(`${prefix}/company`, request.url));
    }
  } catch {
    return NextResponse.next();
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
