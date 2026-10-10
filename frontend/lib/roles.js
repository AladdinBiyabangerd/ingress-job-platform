/**
 * Who may see and use the employer and moderation areas.
 *
 * Roles come from the Academy access token scopes, which the API returns from
 * /api/v1/me as booleans: employer (job:employer), candidate (job:candidate)
 * and staff (job:staff). There is no separate "active account type": an
 * account that holds job:employer may post (the API checks the same scope),
 * even if Academy also gave it job:candidate and STUDENT. A candidate-only
 * account (no employer, no staff) cannot post. Guests see neither tab; company
 * sign-up stays in the "Register" menu, which links to /post after sign-in.
 *
 * `me` is null/undefined until SSR getMe or the client BFF has run, so the
 * restricted tabs stay hidden until identity is known.
 */
export function canPostJobs(me) {
  return Boolean(me?.authenticated && (me.employer || me.staff));
}

export function isStaff(me) {
  return Boolean(me?.authenticated && me.staff);
}

/** Signed in, but only as a candidate: no employer or staff rights. */
export function isCandidateOnly(me) {
  return Boolean(me?.authenticated && !me.employer && !me.staff);
}

/**
 * Public product navbar tabs in display order.
 * Learning (Academy) is an external link rendered by Shell, not a mode.
 * Role-gated links (post, admin, talent) live in AccountBar / side nav.
 */
export function navTabs(_me) {
  return ["browse", "companies", "trends"];
}
