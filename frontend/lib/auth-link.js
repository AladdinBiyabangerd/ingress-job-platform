export function loginHref({ intent, returnTo }) {
  const params = new URLSearchParams();
  if (intent) params.set("intent", intent);
  if (returnTo) params.set("returnTo", returnTo);
  return `/api/auth/login?${params.toString()}`;
}
