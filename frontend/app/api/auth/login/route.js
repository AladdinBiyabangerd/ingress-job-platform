import { createHash, randomBytes } from "node:crypto";
import { NextResponse } from "next/server";
import {
  beginLoginCookies,
  hasSessionCookies,
  noStore,
  oidcConfig,
  safeReturnTo,
  setAuthCookies,
  signedOut,
  STATE_COOKIE,
} from "../../../../lib/server/oidc";

export const runtime = "nodejs";

const INTENTS = new Set(["", "job_employer", "job_candidate"]);

export async function GET(request) {
  const url = new URL(request.url);
  const intent = url.searchParams.get("intent") || "";
  if (!INTENTS.has(intent)) {
    return noStore(Response.json({ error: "invalid_intent" }, { status: 400 }));
  }
  const config = oidcConfig(request);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo"));
  const verifier = randomBytes(32).toString("base64url");
  const challenge = createHash("sha256").update(verifier).digest("base64url");
  const state = randomBytes(16).toString("base64url");
  const nonce = randomBytes(32).toString("base64url");
  const redirectUri = `${config.origin}/api/auth/callback`;

  let saved;
  try {
    saved = await fetch(`${config.apiBase}/api/v1/auth/transactions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        state,
        verifier,
        nonce,
        return_to: returnTo,
        intent,
        redirect_uri: redirectUri,
      }),
      cache: "no-store",
    });
  } catch {
    return noStore(Response.json({ error: "auth_unavailable" }, { status: 503 }));
  }
  if (!saved.ok) return noStore(Response.json({ error: "auth_unavailable" }, { status: 503 }));

  // Only a live post-login session (no guest lock) counts as already signed in.
  const alreadySignedIn = !signedOut(request) && hasSessionCookies(request);
  const params = new URLSearchParams({
    response_type: "code",
    client_id: config.clientId,
    redirect_uri: redirectUri,
    scope: "openid offline_access profile:read job:employer job:candidate job:staff",
    state,
    nonce,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  // Always prompt=login. After job logout, Academy must not silently reuse the
  // portal session — that only stays when existing_account=1 (live job session
  // adding employer/candidate). See ingress-academy portal/oidc/views.py.
  params.set("prompt", "login");
  if (intent) params.set("registration_intent", intent);
  if (intent && alreadySignedIn) params.set("existing_account", "1");
  params.set("return_to", new URL(returnTo, `${config.origin}/`).toString());

  const redirect = NextResponse.redirect(`${config.authorizeUrl}?${params.toString()}`, 302);
  // After logout, keep job_guest until callback succeeds.
  if (signedOut(request)) {
    return noStore(beginLoginCookies(redirect, state, request));
  }
  return noStore(setAuthCookies(redirect, [[STATE_COOKIE, state, 600]], request));
}
