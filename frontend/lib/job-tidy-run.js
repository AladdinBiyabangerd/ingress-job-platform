/** Persist + poll async job_tidy runs across page refresh. */

import { adminPollJobTidy } from "./server/refresh";

export const TIDY_POLL_MS = 1500;
const STORAGE_KEY = "ij:jobTidyRun";

export function rememberTidyJob(jobId) {
  const id = String(jobId || "").trim();
  if (!id || typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* ignore quota / private mode */
  }
}

export function forgetTidyJob() {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function storedTidyJob() {
  if (typeof window === "undefined") return "";
  try {
    return String(window.sessionStorage.getItem(STORAGE_KEY) || "").trim();
  } catch {
    return "";
  }
}

export function progressFromTidy(data, fallbackTotal = 0) {
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
export async function pollTidyJob(
  jobId,
  { onProgress, fallbackTotal = 0, isActive = () => true } = {},
) {
  const id = String(jobId || "").trim();
  if (!id) return { ok: false, last: {} };

  let last = {};
  for (;;) {
    if (!isActive()) return { ok: true, last, cancelled: true };
    const polled = await adminPollJobTidy(id);
    if (!isActive()) return { ok: true, last, cancelled: true };
    if (!polled.ok) return { ok: false, last };
    last = polled.data || {};
    onProgress?.(progressFromTidy(last, fallbackTotal));
    if (last.status !== "queued" && last.status !== "running") {
      return { ok: true, last };
    }
    await sleep(TIDY_POLL_MS);
  }
}
