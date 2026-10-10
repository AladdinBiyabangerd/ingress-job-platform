export function loginHref({ intent, returnTo } = {}) {
  const params = new URLSearchParams();
  if (intent) params.set("intent", intent);
  if (returnTo) params.set("returnTo", returnTo);
  return `/api/auth/login?${params.toString()}`;
}

/**
 * Full page load into the OAuth start route.
 * App Router soft-navigation intercepts same-origin <a href="/api/..."> and
 * cannot follow the 302 to Academy, so the click appears to do nothing.
 */
export function beginLogin(options) {
  window.location.assign(loginHref(options));
}
