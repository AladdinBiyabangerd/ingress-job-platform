import { createHash, randomBytes } from "node:crypto";
import { cookie, noStore, oidcConfig, readCookie, safeReturnTo } from "../../../../lib/server/oidc";

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

  const alreadySignedIn = Boolean(
    readCookie(request, "job_access_token") || readCookie(request, "job_refresh_token"),
  );
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
  // A job session already belongs to an Academy account. Keep that session
  // and pass the role intent; do not force a second registration.
  // New visitors still send prompt=login and land on the join flow.
  if (!(intent && alreadySignedIn)) params.set("prompt", "login");
  if (intent) params.set("registration_intent", intent);
  if (intent && alreadySignedIn) params.set("existing_account", "1");

  const response = new Response(null, {
    status: 302,
    headers: { Location: `${config.authorizeUrl}?${params.toString()}` },
  });
  response.headers.append("Set-Cookie", cookie("job_oidc_state", state, 600));
  response.headers.append("Set-Cookie", cookie("job_access_token", "", 0));
  response.headers.append("Set-Cookie", cookie("job_refresh_token", "", 0));
  return noStore(response);
}
