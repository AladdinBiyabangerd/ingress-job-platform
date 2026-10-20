/**
 * OpenID Connect RP-Initiated Logout 1.0 for Academy.
 * https://openid.net/specs/openid-connect-rpinitiated-1_0.html
 *
 * Job clears its own cookies, then sends the browser to Academy end_session so
 * the Academy (Django) session ends too. Without this, the next "Daxil ol"
 * reused the live Academy session and logged the same person straight back in.
 */

const JWT_SHAPE = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$/;

/** Exact post_logout_redirect_uri registered for job-web: the site root. */
export function postLogoutRedirectUri(origin) {
  return new URL("/", origin).toString();
}

/**
 * Absolute Academy end_session URL, or "" when RP logout is disabled.
 * `idTokenHint` is optional; without it Academy asks the person to confirm.
 */
export function buildEndSessionUrl({
  endSessionUrl,
  clientId,
  idTokenHint = "",
  postLogoutRedirectUri: redirectUri,
  state = "",
}) {
  if (!endSessionUrl) return "";
  let url;
  try {
    url = new URL(endSessionUrl);
  } catch {
    return "";
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return "";
  if (clientId) url.searchParams.set("client_id", clientId);
  const hint = typeof idTokenHint === "string" ? idTokenHint.trim() : "";
  if (hint && hint.length <= 4096 && JWT_SHAPE.test(hint)) {
    url.searchParams.set("id_token_hint", hint);
  }
  if (redirectUri) url.searchParams.set("post_logout_redirect_uri", redirectUri);
  if (state) url.searchParams.set("state", state);
  return url.toString();
}
