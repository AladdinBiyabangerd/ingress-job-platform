/** Cloudflare Turnstile siteverify (server-only). */

export function turnstileSecret() {
  return (process.env.TURNSTILE_SECRET_KEY || "").trim();
}

export function turnstileSiteKey() {
  return (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();
}

export function turnstileRequired() {
  return Boolean(turnstileSecret());
}

export async function verifyTurnstileToken(token, remoteip) {
  const secret = turnstileSecret();
  if (!secret) return true;
  const response = (token || "").trim();
  if (!response) return false;
  const body = new URLSearchParams({ secret, response });
  if (remoteip) body.set("remoteip", remoteip);
  try {
    const res = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const data = await res.json().catch(() => ({}));
    return data?.success === true;
  } catch {
    return false;
  }
}

export async function requireTurnstile(request, token) {
  if (!turnstileRequired()) return null;
  const { getClientIp, slowDownResponse } = await import("./rate-limit");
  const ok = await verifyTurnstileToken(token, getClientIp(request));
  if (ok) return null;
  return slowDownResponse("rateLimit.verifyHuman", 30, 403);
}
