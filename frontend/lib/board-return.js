/** Remember the jobs-board URL (with filters/page) so job pages can return to it. */
export const BOARD_RETURN_KEY = "ij:boardReturn";

const BOARD_PATHS = new Set(["/", "/en", "/ru"]);

/** True for a same-origin board path ("/", "/en", "/ru") with optional query. */
export function isBoardReturnUrl(value) {
  const s = String(value || "");
  if (!s.startsWith("/") || s.startsWith("//")) return false;
  const path = s.split(/[?#]/)[0].replace(/\/+$/, "") || "/";
  return BOARD_PATHS.has(path);
}

/** Pick the saved board URL if it belongs to this locale, else the fallback. */
export function boardReturnHref(saved, fallback) {
  const s = saved && typeof saved === "object" ? saved.url : saved;
  if (!isBoardReturnUrl(s)) return fallback;
  const path = String(s).split(/[?#]/)[0].replace(/\/+$/, "") || "/";
  const fb = String(fallback || "/").replace(/\/+$/, "") || "/";
  return path === fb ? s : fallback;
}

export function saveBoardReturn(url, scrollY = 0) {
  try {
    if (!isBoardReturnUrl(url)) return;
    window.sessionStorage.setItem(BOARD_RETURN_KEY, JSON.stringify({ url, scrollY: Math.max(0, Math.round(Number(scrollY) || 0)) }));
  } catch {}
}

export function readBoardReturn() {
  try {
    const raw = window.sessionStorage.getItem(BOARD_RETURN_KEY);
    const data = raw ? JSON.parse(raw) : null;
    return data && isBoardReturnUrl(data.url) ? data : null;
  } catch {
    return null;
  }
}
