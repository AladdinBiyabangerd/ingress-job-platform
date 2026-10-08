/** Browser Web Push helpers (settings + SW subscribe). */

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

export function pushSupported() {
  if (typeof window === "undefined") return false;
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export async function registerPushWorker() {
  if (!pushSupported()) {
    throw new Error("unsupported");
  }
  return navigator.serviceWorker.register("/sw.js", { scope: "/" });
}

export async function fetchVapidPublicKey() {
  const res = await fetch("/api/auth/me/push-vapid-key", { cache: "no-store" });
  if (!res.ok) {
    const err = new Error("vapid_unavailable");
    err.status = res.status;
    throw err;
  }
  const data = await res.json();
  const key = data && data.publicKey;
  if (!key) throw new Error("vapid_missing");
  return key;
}

export async function savePushSubscription(subscription) {
  const json = typeof subscription.toJSON === "function" ? subscription.toJSON() : subscription;
  const res = await fetch("/api/auth/me/push-subscription", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: json.endpoint,
      keys: {
        p256dh: json.keys && json.keys.p256dh,
        auth: json.keys && json.keys.auth,
      },
    }),
  });
  if (!res.ok) {
    const err = new Error("subscribe_failed");
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function removePushSubscription(endpoint) {
  if (!endpoint) return { deleted: false };
  const res = await fetch("/api/auth/me/push-subscription", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint }),
  });
  if (!res.ok) {
    const err = new Error("unsubscribe_failed");
    err.status = res.status;
    throw err;
  }
  return res.json();
}

/**
 * Request permission, subscribe, and persist on the API.
 * @returns {{ ok: true, endpoint: string } | { ok: false, reason: string }}
 */
export async function enableBrowserPush() {
  if (!pushSupported()) {
    return { ok: false, reason: "unsupported" };
  }
  await registerPushWorker();
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return { ok: false, reason: permission === "denied" ? "denied" : "permission" };
  }
  let publicKey;
  try {
    publicKey = await fetchVapidPublicKey();
  } catch {
    return { ok: false, reason: "vapid" };
  }
  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }
  await savePushSubscription(sub);
  return { ok: true, endpoint: sub.endpoint };
}

export async function disableBrowserPush() {
  if (!pushSupported()) {
    return { ok: true };
  }
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      const endpoint = sub.endpoint;
      try {
        await sub.unsubscribe();
      } catch {
        /* ignore local unsubscribe errors */
      }
      await removePushSubscription(endpoint);
    }
  } catch {
    /* soft-fail */
  }
  return { ok: true };
}
