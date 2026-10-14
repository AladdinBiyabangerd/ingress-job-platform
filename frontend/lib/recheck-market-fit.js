/** Persist + poll async market-fit recheck jobs across page refresh. */

import { adminPollRecheckMarketFit } from "./server/refresh";

export const RECHECK_POLL_MS = 1500;

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
  return { total, done, remaining };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Poll until the job leaves queued/running, or isActive() returns false.
 * @returns {{ ok: boolean, last: object, cancelled?: boolean }}
 */
export async function pollRecheckJob(
  jobId,
  { onProgress, fallbackTotal = 0, isActive = () => true } = {},
) {
  const id = String(jobId || "").trim();
  if (!id) return { ok: false, last: {} };

  let last = {};
  for (;;) {
    if (!isActive()) return { ok: true, last, cancelled: true };
    const polled = await adminPollRecheckMarketFit(id);
    if (!isActive()) return { ok: true, last, cancelled: true };
    if (!polled.ok) return { ok: false, last };
    last = polled.data || {};
    onProgress?.(progressFromRecheck(last, fallbackTotal));
    if (last.status !== "queued" && last.status !== "running") {
      return { ok: true, last };
    }
    await sleep(RECHECK_POLL_MS);
  }
}
