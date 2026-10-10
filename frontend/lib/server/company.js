import { cache } from "react";
import { hrefFor } from "../copy";
import { getMe } from "./me";

const EMPTY_PROFILE = {
  company_name: "",
  city: "",
  about: "",
  address: "",
  website: "",
  industry: "",
  size: "",
  complete: false,
};

export function companyLoginPath(locale) {
  // No registration_intent: session restore must not re-grant JOB_EMPLOYER after
  // staff revoked it. Become-employer CTAs elsewhere still send job_employer.
  return `/api/auth/login?returnTo=${encodeURIComponent(hrefFor(locale, { mode: "company" }))}`;
}

export function isGuestMe(me) {
  return Boolean(me && typeof me === "object" && !me.authenticated);
}

/**
 * Company profile fields for /company. Uses GET /me (already includes
 * company_profile). Guests skip FastAPI via getMe. Expired access returns
 * null so the client BFF can refresh.
 */
export const getCompanyProfile = cache(async () => {
  const me = await getMe();
  if (me == null) return { me: null, profile: null };
  if (!me.authenticated) return { me, profile: null };
  const raw = me.company_profile;
  const profile = raw && typeof raw === "object" ? raw : EMPTY_PROFILE;
  return { me, profile };
});
