import { createHash, randomBytes } from "node:crypto";
import { NextResponse } from "next/server";
import { buildAuthorizeQuery, buildLoginRedirectUrl } from "../../../../lib/oidc-authorize";
import { employerPostingEnabled } from "../../../../lib/product-features";
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
import {
  assertRateLimit,
  getClientIp,
  slowDownResponse,
} from "../../../../lib/server/rate-limit";
import {
  turnstileRequired,
  turnstileSiteKey,
  verifyTurnstileToken,
} from "../../../../lib/server/turnstile";

export const runtime = "nodejs";

const INTENTS = new Set(["", "job_employer", "job_candidate"]);

function turnstileGateHtml(actionUrl, siteKey) {
  const safeAction = String(actionUrl).replace(/"/g, "&quot;");
  const safeKey = String(siteKey).replace(/"/g, "&quot;");
  return `<!doctype html>
<html lang="az"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ingress Job</title>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<style>
  body{font-family:system-ui,sans-serif;margin:0;min-height:100vh;display:grid;place-items:center;background:#f7f5f1;color:#1a1a1a}
  main{max-width:22rem;padding:1.5rem;text-align:center}
  p{line-height:1.45;font-size:0.95rem}
</style></head>
<body><main>
<p>Girişi sizin üçün təhlükəsiz saxlamaq üçün qısa yoxlama…</p>
<form id="f" method="get" action="${safeAction}">
<div class="cf-turnstile" data-sitekey="${safeKey}" data-callback="onTok"></div>
</form>
<script>
function onTok(token){
  var f=document.getElementById("f");
  var i=document.createElement("input");
  i.type="hidden"; i.name="cf_turnstile_response"; i.value=token;
  f.appendChild(i); f.submit();
}
</script>
</main></body></html>`;
}

export async function GET(request) {
  const limited = await assertRateLimit(request, "auth_tx");
  if (limited) return noStore(limited);
  const url = new URL(request.url);
  const intent = url.searchParams.get("intent") || "";
  if (!INTENTS.has(intent)) {
    return noStore(Response.json({ error: "invalid_intent" }, { status: 400 }));
  }
  if (intent === "job_employer" && !employerPostingEnabled()) {
    return noStore(Response.json({ error: "employer_posting_parked" }, { status: 404 }));
  }
  const token =
    url.searchParams.get("cf_turnstile_response") || url.searchParams.get("turnstile_token");
  if (turnstileRequired()) {
    const siteKey = turnstileSiteKey();
    if (!token) {
      if (!siteKey) {
        return noStore(slowDownResponse("rateLimit.verifyHuman", 30, 503));
      }
      const action = new URL(url.pathname + url.search, url.origin);
      return noStore(
        new NextResponse(turnstileGateHtml(action.toString(), siteKey), {
          status: 200,
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
      );
    }
    const ok = await verifyTurnstileToken(token, getClientIp(request));
    if (!ok) return noStore(slowDownResponse("rateLimit.verifyHuman", 30, 403));
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
  const returnToAbsolute = new URL(returnTo, `${config.origin}/`).toString();
  const params = buildAuthorizeQuery({
    clientId: config.clientId,
    redirectUri,
    state,
    nonce,
    challenge,
    intent,
    returnToAbsolute,
    signedOut: signedOut(request),
    alreadySignedIn,
  });

  // Live Job session + role intent → authorize (existing_account). Guests → job-account.
  const loginUrl = buildLoginRedirectUrl({
    jobAccountUrl: config.jobAccountUrl,
    authorizeUrl: config.authorizeUrl,
    authorizeParams: params,
    intent,
    returnToAbsolute,
    alreadySignedIn,
  });
  const redirect = NextResponse.redirect(loginUrl, 302);
  // After logout, keep job_guest until callback succeeds.
  if (signedOut(request)) {
    return noStore(beginLoginCookies(redirect, state, request));
  }
  return noStore(setAuthCookies(redirect, [[STATE_COOKIE, state, 600]], request));
}
