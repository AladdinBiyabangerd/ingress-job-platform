import { apiBase } from "../../../../../lib/api";

export const runtime = "nodejs";

/**
 * Chrome extension import. The API has no public host, so the extension posts
 * to the web origin and this handler forwards to the API with the token header.
 */
const EXT_ORIGIN = /^chrome-extension:\/\/[a-z]{32}$/;

function cors(request) {
  const origin = request.headers.get("origin") || "";
  const headers = { "Cache-Control": "no-store", Vary: "Origin" };
  if (EXT_ORIGIN.test(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    headers["Access-Control-Allow-Headers"] = "Content-Type, X-Import-Token, Authorization";
    headers["Access-Control-Max-Age"] = "600";
  }
  return headers;
}

export async function OPTIONS(request) {
  return new Response(null, { status: 204, headers: cors(request) });
}

export async function POST(request) {
  const headers = { "Content-Type": "application/json", Accept: "application/json" };
  const token = request.headers.get("x-import-token");
  const auth = request.headers.get("authorization");
  if (token) headers["X-Import-Token"] = token;
  if (auth) headers.Authorization = auth;
  try {
    const res = await fetch(`${apiBase()}/api/v1/import/linkedin-jobs`, {
      method: "POST",
      headers,
      body: await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
    const payload = await res.json().catch(() => ({}));
    return Response.json(payload, { status: res.status, headers: cors(request) });
  } catch (err) {
    console.error("[api/v1/import/linkedin-jobs] upstream failed", {
      message: err instanceof Error ? err.message : String(err),
    });
    return Response.json({ detail: "upstream_unreachable" }, { status: 502, headers: cors(request) });
  }
}
