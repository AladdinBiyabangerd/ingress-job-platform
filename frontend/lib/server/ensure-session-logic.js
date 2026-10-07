/** Pure session ensure helpers (no Next.js imports — unit-testable). */

export const EXP_SKEW_SECONDS = 120;

export function shouldRefreshAccess({ access, expUnix, now, force = false }) {
  if (force) return true;
  if (!access) return true;
  if (!Number.isFinite(expUnix)) return true;
  return expUnix <= now + EXP_SKEW_SECONDS;
}

export function sessionEntriesFromTokens(data, { now = Math.floor(Date.now() / 1000), clampAge } = {}) {
  const expiresIn = clampAge(data.expires_in, 900, 3600);
  const entries = [
    ["job_at", data.access_token, expiresIn],
    ["job_exp", String(now + expiresIn), expiresIn],
  ];
  if (data.refresh_token) {
    entries.push([
      "job_rt",
      data.refresh_token,
      clampAge(data.refresh_expires_in, 3600, 365 * 24 * 60 * 60),
    ]);
  }
  return entries;
}

/**
 * Ensure a usable access token from cookie values.
 * @returns {{ access: string|null, cookieEntries: Array, guest: boolean, kept: boolean }}
 *   `kept` true when 5xx left existing cookies untouched.
 */
export async function ensureSessionLogic({
  getCookie,
  fetchFn,
  apiBaseUrl,
  force = false,
  now = Math.floor(Date.now() / 1000),
  clampAge,
  clearEntries,
}) {
  if (getCookie("job_guest")) {
    return { access: null, cookieEntries: [], guest: true, kept: false };
  }

  const access = getCookie("job_at");
  const expUnix = Number(getCookie("job_exp"));
  if (!shouldRefreshAccess({ access, expUnix, now, force })) {
    return { access, cookieEntries: [], guest: false, kept: false };
  }

  const refresh = getCookie("job_rt");
  if (!refresh) {
    if (access && !force) {
      return { access, cookieEntries: [], guest: false, kept: false };
    }
    return {
      access: null,
      cookieEntries: access ? clearEntries() : [],
      guest: false,
      kept: false,
    };
  }

  let refreshed;
  try {
    refreshed = await fetchFn(`${apiBaseUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
  } catch {
    return { access: access || null, cookieEntries: [], guest: false, kept: true };
  }

  if (!refreshed.ok) {
    if (refreshed.status === 401) {
      return { access: null, cookieEntries: clearEntries(), guest: false, kept: false };
    }
    // 5xx / other — keep cookies; return existing access if any.
    return { access: access || null, cookieEntries: [], guest: false, kept: true };
  }

  const data = await refreshed.json();
  if (!data?.access_token) {
    return { access: null, cookieEntries: clearEntries(), guest: false, kept: false };
  }
  const cookieEntries = sessionEntriesFromTokens(data, { now, clampAge });
  return { access: data.access_token, cookieEntries, guest: false, kept: false };
}
