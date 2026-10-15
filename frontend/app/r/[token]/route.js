import { NextResponse } from "next/server";
import { apiBase } from "../../../lib/api";
import { noStore, publicOrigin } from "../../../lib/server/oidc";

export const runtime = "nodejs";

const JOB_PATH = /^\/(?:en\/|ru\/)?jobs\/\d+\/?$/;

/** Only allow on-site job detail redirects (no open redirects). */
function jobRedirectTarget(location, request) {
  if (!location) return null;
  try {
    const origin = publicOrigin(request);
    const url = new URL(location, origin);
    if (!JOB_PATH.test(url.pathname)) return null;
    return new URL(`${url.pathname}${url.search}${url.hash}`, origin);
  } catch {
    return null;
  }
}

/** Proxy email click tracking → API 302 to the job page. */
export async function GET(request, { params }) {
  const resolved = (await params) || {};
  const raw = resolved.token;
  const token = String(Array.isArray(raw) ? raw[0] : raw || "").trim();
  if (!token) {
    return noStore(NextResponse.json({ detail: "invalid_token" }, { status: 404 }));
  }

  let res;
  try {
    res = await fetch(`${apiBase()}/api/v1/r/${encodeURIComponent(token)}`, {
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return noStore(NextResponse.json({ detail: "upstream_unavailable" }, { status: 502 }));
  }

  const location = res.headers.get("location");
  if (res.status >= 300 && res.status < 400) {
    const target = jobRedirectTarget(location, request);
    if (target) {
      return noStore(NextResponse.redirect(target, 302));
    }
  }

  const payload = await res.json().catch(() => ({ detail: "invalid_token" }));
  const status = res.status >= 400 ? res.status : 404;
  return noStore(NextResponse.json(payload, { status }));
}
