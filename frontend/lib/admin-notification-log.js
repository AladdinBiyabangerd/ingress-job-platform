// Pure helpers for the staff «Bildiriş jurnalı» tab (admin-notification-log.js).

export const NOTIF_LOG_DAYS = [7, 30, 90];

export function clampDays(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 30;
  return Math.max(1, Math.min(90, Math.trunc(raw)));
}

export function notificationLogQuery({ user = "", days = 30 } = {}) {
  const params = new URLSearchParams();
  const who = String(user || "").trim().slice(0, 255);
  if (who) params.set("user", who);
  params.set("days", String(clampDays(days)));
  return params.toString();
}

// sent → ok, failed → bad, sending/queued → wait, anything else → muted.
export function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "sent") return "ok";
  if (value === "failed") return "bad";
  if (value === "sending") return "wait";
  return "muted";
}

export function notifKindLabel(t, kind) {
  const value = String(kind || "");
  const base = value.endsWith("_email") ? value.slice(0, -"_email".length) : value;
  const labels = t.notifLogKinds || {};
  const label = labels[base] || base;
  return value.endsWith("_email") ? `${label} · ${t.notifLogEmailSuffix || "email"}` : label;
}

export function notifReasonLabel(t, reason) {
  const value = String(reason || "");
  if (!value) return "";
  const labels = t.notifLogReasons || {};
  const [head, ...rest] = value.split(":");
  const tail = rest.join(":");
  const key = head.startsWith("send_failed") ? "send_failed" : head;
  const label = labels[key] || labels[value] || value;
  return tail ? `${label} (${tail})` : label;
}

export function weekdayLabel(t, day) {
  const names = t.notifLogWeekdays || [];
  const n = Number(day);
  return Number.isInteger(n) && names[n] ? names[n] : String(day ?? "");
}
