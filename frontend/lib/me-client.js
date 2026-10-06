/** Shared client session fetch: in-flight dedupe + short sessionStorage TTL. */

const CACHE_KEY = "ij_me_cache";
const TTL_MS = 30_000;

let inflight = null;

function readCache() {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    if (Date.now() - Number(parsed.at || 0) > TTL_MS) return null;
    return parsed.data ?? null;
  } catch {
    return null;
  }
}

function writeCache(data) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data }));
  } catch {
    // Private mode / quota — ignore.
  }
}

export function seedMeCache(data) {
  if (!data || typeof data !== "object") return;
  writeCache(data);
}

export function clearMeCache() {
  inflight = null;
  try {
    sessionStorage.removeItem(CACHE_KEY);
  } catch {
    // ignore
  }
}

/** One GET /api/auth/me per tab burst; skipped when SSR already seeded the cache. */
export function fetchMe() {
  const cached = readCache();
  if (cached) return Promise.resolve(cached);
  if (inflight) return inflight;
  inflight = fetch(`/api/auth/me?lang=${encodeURIComponent(document.documentElement.lang || "az")}`, { cache: "no-store" })
    .then((res) => res.json())
    .then((data) => {
      writeCache(data);
      return data;
    })
    .catch(() => ({ authenticated: false }))
    .finally(() => {
      inflight = null;
    });
  return inflight;
}
