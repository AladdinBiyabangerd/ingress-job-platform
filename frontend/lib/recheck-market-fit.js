/** Persist + poll async market-fit recheck jobs across page refresh. */

import { adminPollRecheckMarketFit } from "./server/refresh";

export const RECHECK_POLL_MS = 1500;
/** Max ads per fresh «AI ilə yenidən yoxla» run (API FRESH_MAX_IDS). */
export const RECHECK_FRESH_MAX = 200;
export const RECHECK_DEFAULT_LIMIT = 50;
/** Matches API stale window (~90s) + a little slack for slow polls. */
export const RECHECK_STALE_MS = 105_000;

function storageKey(scope) {
  const s =
    scope === "crawled" ? "crawled" : scope === "crawl_rejects" ? "crawl_rejects" : "queue";
  return `ij:marketFitRecheck:${s}`;
}

export function rememberRecheckJob(scope, jobId) {
  const id = String(jobId || "").trim();
  if (!id || typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(storageKey(scope), id);
  } catch {
    /* ignore quota / private mode */
  }
}

export function forgetRecheckJob(scope) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(storageKey(scope));
  } catch {
    /* ignore */
  }
}

export function storedRecheckJob(scope) {
  if (typeof window === "undefined") return "";
  try {
    return String(window.sessionStorage.getItem(storageKey(scope)) || "").trim();
  } catch {
    return "";
  }
}

export function progressFromRecheck(data, fallbackTotal = 0) {
  const total = Number(data?.total) || fallbackTotal || 0;
  const done = Number(data?.done) || 0;
  const remaining =
    data?.remaining != null && data.remaining !== ""
      ? Number(data.remaining) || 0
      : Math.max(0, total - done);
  return {
    total,
    done,
    remaining,
    status: String(data?.status || ""),
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Poll until the job leaves queued/running/cancelling, or isActive() returns false.
 * If status stays active with no terminal result past RECHECK_STALE_MS, treat as
 * cancelled so the UI cannot stick on «Dayandırılır…» after a dead worker.
 * @returns {{ ok: boolean, last: object, cancelled?: boolean }}
 */
export async function pollRecheckJob(
  jobId,
  { onProgress, onStatus, fallbackTotal = 0, isActive = () => true } = {},
) {
  const id = String(jobId || "").trim();
  if (!id) return { ok: false, last: {} };

  let last = {};
  const startedAt = Date.now();
  let lastProgressAt = startedAt;
  let lastDone = -1;

  for (;;) {
    if (!isActive()) return { ok: true, last, cancelled: true };
    const polled = await adminPollRecheckMarketFit(id);
    if (!isActive()) return { ok: true, last, cancelled: true };
    if (!polled.ok) return { ok: false, last };
    last = polled.data || {};
    const progress = progressFromRecheck(last, fallbackTotal);
    onProgress?.(progress);
    onStatus?.(String(last.status || ""));

    const done = progress.done;
    if (done !== lastDone) {
      lastDone = done;
      lastProgressAt = Date.now();
    }

    // cancelling: stop requested; keep polling until worker finishes in-flight ad
    if (
      last.status !== "queued" &&
      last.status !== "running" &&
      last.status !== "cancelling"
    ) {
      return { ok: true, last };
    }

    const idleMs = Date.now() - lastProgressAt;
    if (idleMs >= RECHECK_STALE_MS) {
      return {
        ok: true,
        last: {
          ...last,
          status: last.status === "cancelling" ? "cancelled" : "failed",
          error: String(last.error || "stale_worker").slice(0, 300),
        },
      };
    }
    await sleep(RECHECK_POLL_MS);
  }
}
