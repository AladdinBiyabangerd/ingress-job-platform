/** Query string for Academy /portal/oauth/authorize. */

export const JOB_OIDC_SCOPE =
  "openid offline_access profile:read job:employer job:candidate job:staff";

export function buildAuthorizeQuery({
  clientId,
  redirectUri,
  state,
  nonce,
  challenge,
  intent = "",
  returnToAbsolute = "",
  signedOut = false,
  alreadySignedIn = false,
}) {
  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: JOB_OIDC_SCOPE,
    state,
    nonce,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  // prompt=login only after Job logout (guest lock). Sending it on every
  // Register click logged the person out of Academy and broke SSO.
  if (signedOut) params.set("prompt", "login");
  if (intent) params.set("registration_intent", intent);
  if (intent && alreadySignedIn) params.set("existing_account", "1");
  if (returnToAbsolute) params.set("return_to", returnToAbsolute);
  return params;
}
