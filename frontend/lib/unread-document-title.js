/** Browser tab title badge: "(2) Ingress Job — …" like Instagram / YouTube. */

export const UNREAD_NOTIFICATIONS_EVENT = "ingress:unread-notifications";

const COUNT_PREFIX = /^\((\d+\+?)\)\s+/;

export function stripUnreadTitlePrefix(title) {
  return String(title || "").replace(COUNT_PREFIX, "");
}

export function formatUnreadDocumentTitle(baseTitle, unread) {
  const base = stripUnreadTitlePrefix(baseTitle).trim() || "Ingress Job";
  const n = Math.max(0, Math.floor(Number(unread) || 0));
  if (n <= 0) return base;
  const label = n > 99 ? "99+" : String(n);
  return `(${label}) ${base}`;
}

export function applyUnreadDocumentTitle(unread) {
  if (typeof document === "undefined") return;
  const next = formatUnreadDocumentTitle(document.title, unread);
  if (document.title !== next) document.title = next;
}

export function publishUnreadNotifications(unread) {
  if (typeof window === "undefined") return;
  const n = Math.max(0, Math.floor(Number(unread) || 0));
  window.dispatchEvent(new CustomEvent(UNREAD_NOTIFICATIONS_EVENT, { detail: { unread: n } }));
}
